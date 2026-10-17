"""Optional single-owner OAuth for Claude Web, using the MCP SDK's protocol handlers.

No accounts/database: registrations and grants expire in memory; restart means reconnect.
The owner approves with a separate local password, never the MCP bearer token.
"""

import html
import re
import secrets
import time
from urllib.parse import urlencode, urlsplit

from mcp.server.auth.provider import (
    AccessToken, AuthorizationCode, AuthorizeError, RefreshToken,
    RegistrationError, TokenError, construct_redirect_uri,
)
from mcp.server.auth.routes import create_auth_routes, create_protected_resource_routes, build_metadata, cors_middleware
from mcp.server.auth.handlers.metadata import MetadataHandler
from mcp.server.auth.handlers.token import TokenHandler
from mcp.server.auth.middleware.client_auth import ClientAuthenticator, AuthenticationError
from mcp.server.transport_security import RequestBodyLimitMiddleware
from mcp.server.auth.settings import ClientRegistrationOptions, RevocationOptions
from mcp.shared.auth import OAuthToken
from pydantic import AnyHttpUrl
from starlette.applications import Starlette
from starlette.middleware.trustedhost import TrustedHostMiddleware
from starlette.responses import HTMLResponse, JSONResponse, RedirectResponse
from starlette.routing import Route

CALLBACK = "https://claude.ai/api/mcp/auth_callback"
SCOPES = ["files", "offline_access"]
PAGE_HEADERS = {
    "Cache-Control": "no-store", "Referrer-Policy": "no-referrer",
    "Content-Security-Policy": "default-src 'none'; form-action 'self'; frame-ancestors 'none'",
    "X-Content-Type-Options": "nosniff",
}


class OwnerOAuth:
    def __init__(self, issuer, password):
        self.issuer = issuer.rstrip("/")
        self.resource = self.issuer + "/mcp"
        self.password = password
        self.clients, self.pending, self.codes = {}, {}, {}
        self.access, self.refresh = {}, {}
        self.failures = []

    def prune(self):
        now = time.time()
        for store in (self.clients, self.pending):
            for key, value in list(store.items()):
                if value[0] <= now:
                    del store[key]
        for store in (self.codes, self.access, self.refresh):
            for key, value in list(store.items()):
                if value.expires_at <= now:
                    del store[key]
        self.failures = [t for t in self.failures if t > now - 60]

    async def get_client(self, client_id):
        self.prune()
        record = self.clients.get(client_id)
        return record[1] if record else None

    async def register_client(self, client_info):
        self.prune()
        # This integration serves Claude Web only. Do not trust arbitrary redirect hosts.
        if [str(u) for u in client_info.redirect_uris] != [CALLBACK]:
            raise RegistrationError("invalid_redirect_uri", "Only Claude Web's callback is allowed.")
        if len(self.clients) >= 100:
            raise RegistrationError("invalid_client_metadata", "Registration limit reached; restart the server.")
        self.clients[client_info.client_id] = (time.time() + 86400, client_info)

    async def authorize(self, client, params):
        self.prune()
        if params.resource not in (None, self.resource):
            raise AuthorizeError("invalid_target", "Wrong MCP resource.")
        if not re.fullmatch(r"[A-Za-z0-9_-]{43}", params.code_challenge):
            raise AuthorizeError("invalid_request", "An S256 PKCE challenge is required.")
        if len(self.pending) >= 100:
            raise AuthorizeError("temporarily_unavailable", "Too many pending approvals.")
        ticket = secrets.token_urlsafe(32)
        self.pending[ticket] = (time.time() + 300, client, params)
        return self.issuer + "/consent?" + urlencode({"ticket": ticket})

    async def consent(self, request):
        self.prune()
        if request.method == "GET":
            ticket = request.query_params.get("ticket", "")
            record = self.pending.get(ticket)
            if not record:
                return HTMLResponse("Approval expired. Reconnect in Claude.", 400, headers=PAGE_HEADERS)
            csrf = secrets.token_urlsafe(32)
            # Cookie and hidden value bind the POST to the browser that opened this page.
            page = f'''<!doctype html><html lang="en"><meta charset="utf-8">
<meta name="viewport" content="width=device-width"><title>Connect CSE2 File Server</title>
<body><main><h1>Connect CSE2 File Server</h1>
<p>Allow Claude to read, create, edit and delete permitted text files inside this project's workspace.</p>
<p>This is your single-owner classroom server. Return address: <strong>claude.ai</strong>.</p>
<p>Enter the local connection password from <code>.local/oauth-login-code.txt</code>.</p>
<form method="post" action="/consent">
<input type="hidden" name="ticket" value="{html.escape(ticket, quote=True)}">
<input type="hidden" name="csrf" value="{csrf}">
<p><label>Connection password <input name="password" type="password" required autocomplete="off"></label></p>
<button name="decision" value="allow">Allow Claude</button>
<button name="decision" value="deny" formnovalidate>Cancel</button></form></main></body></html>'''
            response = HTMLResponse(page, headers=PAGE_HEADERS)
            response.set_cookie("cse2_csrf", csrf, max_age=300, httponly=True,
                                secure=self.issuer.startswith("https:"), samesite="lax", path="/consent")
            return response
        if request.headers.get("origin") != self.issuer:
            return JSONResponse({"error": "Invalid approval origin."}, 403, headers=PAGE_HEADERS)
        form = await request.form(max_fields=5)
        ticket = str(form.get("ticket", ""))
        record = self.pending.get(ticket)
        csrf = str(form.get("csrf", ""))
        if not record or not csrf or not secrets.compare_digest(csrf, request.cookies.get("cse2_csrf", "")):
            return JSONResponse({"error": "Approval expired or invalid."}, 400, headers=PAGE_HEADERS)
        _, client, params = record
        if form.get("decision") == "deny":
            del self.pending[ticket]
            return RedirectResponse(construct_redirect_uri(str(params.redirect_uri), error="access_denied",
                                    state=params.state), 302, headers=PAGE_HEADERS)
        if len(self.failures) >= 5:
            return JSONResponse({"error": "Too many attempts. Wait one minute, then reconnect."}, 429, headers=PAGE_HEADERS)
        if not secrets.compare_digest(str(form.get("password", "")).encode(), self.password.encode()):
            self.failures.append(time.time())
            return HTMLResponse("Incorrect password. Go back and try again.", 403, headers=PAGE_HEADERS)
        if len(self.codes) >= 200:
            return HTMLResponse("Too many approvals. Wait two minutes, then reconnect.", 429, headers=PAGE_HEADERS)
        del self.pending[ticket]
        code = secrets.token_urlsafe(32)
        self.codes[code] = AuthorizationCode(code=code, client_id=client.client_id,
            scopes=params.scopes or ["files"], expires_at=time.time() + 120,
            code_challenge=params.code_challenge, redirect_uri=params.redirect_uri,
            redirect_uri_provided_explicitly=params.redirect_uri_provided_explicitly,
            resource=self.resource, subject="owner")
        response = RedirectResponse(construct_redirect_uri(str(params.redirect_uri), code=code,
                                    state=params.state), 302, headers=PAGE_HEADERS)
        response.delete_cookie("cse2_csrf", path="/consent")
        return response

    async def load_authorization_code(self, client, authorization_code):
        self.prune()
        return self.codes.get(authorization_code)

    def issue(self, client, scopes):
        self.prune()
        if len(self.access) >= 200 or len(self.refresh) >= 200:
            raise TokenError("invalid_grant", "Session limit reached; restart and reconnect.")
        access, refresh = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
        common = dict(client_id=client.client_id, scopes=scopes, resource=self.resource, subject="owner")
        self.access[access] = AccessToken(token=access, expires_at=int(time.time()) + 3600, **common)
        self.refresh[refresh] = RefreshToken(token=refresh, expires_at=int(time.time()) + 86400, **common)
        return OAuthToken(access_token=access, token_type="Bearer", expires_in=3600,
                          refresh_token=refresh, scope=" ".join(scopes))

    async def exchange_authorization_code(self, client, authorization_code):
        if self.codes.pop(authorization_code.code, None) is None:
            raise TokenError("invalid_grant", "Authorization code already used.")
        return self.issue(client, authorization_code.scopes)

    async def load_refresh_token(self, client, refresh_token):
        self.prune()
        return self.refresh.get(refresh_token)

    async def exchange_refresh_token(self, client, refresh_token, scopes):
        if self.refresh.pop(refresh_token.token, None) is None:
            raise TokenError("invalid_grant", "Refresh token already used.")
        return self.issue(client, scopes)

    async def load_access_token(self, token):
        self.prune()
        return self.access.get(token)

    async def revoke_token(self, token):
        # Single owner: revoke the client's complete grant, including rotated tokens.
        for store in (self.access, self.refresh):
            for key, value in list(store.items()):
                if value.client_id == token.client_id:
                    del store[key]

    async def token_endpoint(self, request):
        form = await request.form()
        if form.get("resource") not in (None, self.resource):
            return JSONResponse({"error": "invalid_target"}, 400, headers={"Cache-Control": "no-store"})
        return await TokenHandler(self, ClientAuthenticator(self)).handle(request)

    async def revoke_endpoint(self, request):
        # SDK 2.3's revocation schema requires client_secret even for public clients.
        # Authenticate with its shared authenticator, then apply RFC 7009 directly.
        try:
            client = await ClientAuthenticator(self).authenticate_request(request)
        except AuthenticationError:
            return JSONResponse({"error": "invalid_client"}, 401)
        form = await request.form()
        if not isinstance(form.get("token"), str):
            return JSONResponse({"error": "invalid_request"}, 400)
        token = await self.load_access_token(form["token"]) or await self.load_refresh_token(client, form["token"])
        if token and token.client_id == client.client_id:
            await self.revoke_token(token)
        return JSONResponse({}, headers={"Cache-Control": "no-store"})

    def app(self):
        options = ClientRegistrationOptions(enabled=True, valid_scopes=SCOPES, default_scopes=["files"])
        routes = create_auth_routes(self, AnyHttpUrl(self.issuer),
            client_registration_options=options,
            revocation_options=RevocationOptions(enabled=True))
        metadata = build_metadata(AnyHttpUrl(self.issuer), None, options, RevocationOptions(enabled=True))
        metadata.token_endpoint_auth_methods_supported.append("none")
        routes[0] = Route("/.well-known/oauth-authorization-server",
            cors_middleware(MetadataHandler(metadata).handle, ["GET", "OPTIONS"]), methods=["GET", "OPTIONS"])
        routes = [r for r in routes if r.path not in ("/token", "/revoke")]
        routes += [Route("/token", cors_middleware(self.token_endpoint, ["POST", "OPTIONS"]), methods=["POST", "OPTIONS"]),
                   Route("/revoke", cors_middleware(self.revoke_endpoint, ["POST", "OPTIONS"]), methods=["POST", "OPTIONS"])]
        routes += create_protected_resource_routes(AnyHttpUrl(self.resource),
            [AnyHttpUrl(self.issuer)], scopes_supported=SCOPES, resource_name="CSE2 File Server")
        routes.append(Route("/consent", self.consent, methods=["GET", "POST"]))
        app = TrustedHostMiddleware(Starlette(routes=routes),
            allowed_hosts=["127.0.0.1", "localhost", urlsplit(self.issuer).hostname])
        return RequestBodyLimitMiddleware(app, 16384)
