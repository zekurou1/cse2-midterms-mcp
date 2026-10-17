"""Check owner consent and a real MCP call through HTTPS, without printing credentials."""

import asyncio
import base64
import hashlib
import json
import re
import secrets
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import httpx2
from dotenv import dotenv_values
from mcp import Client
from mcp.client.streamable_http import streamable_http_client

BASE = Path(__file__).resolve().parents[1]
CALLBACK = "https://claude.ai/api/mcp/auth_callback"


async def main():
    config = dotenv_values(BASE / ".env")
    issuer = config["OAUTH_ISSUER_URL"].rstrip("/")
    url = issuer + "/mcp"
    verifier = secrets.token_urlsafe(48)
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip("=")
    async with httpx2.AsyncClient(timeout=20, follow_redirects=False) as http:
        anonymous = await http.get(url)
        assert anonymous.status_code == 401 and "resource_metadata=" in anonymous.headers["www-authenticate"]
        metadata = (await http.get(issuer + "/.well-known/oauth-authorization-server")).json()
        resource = (await http.get(issuer + "/.well-known/oauth-protected-resource/mcp")).json()
        assert resource["resource"] == url and metadata["code_challenge_methods_supported"] == ["S256"]
        registration = await http.post(issuer + "/register", json={"redirect_uris": [CALLBACK],
            "token_endpoint_auth_method": "none", "grant_types": ["authorization_code", "refresh_token"],
            "response_types": ["code"], "scope": "files offline_access"})
        assert registration.status_code == 201
        client_id = registration.json()["client_id"]
        auth = await http.get(issuer + "/authorize", params=dict(client_id=client_id, response_type="code",
            redirect_uri=CALLBACK, state="oauth-check", resource=url, scope="files offline_access",
            code_challenge=challenge, code_challenge_method="S256"))
        assert auth.status_code == 302
        consent = await http.get(auth.headers["location"])
        assert consent.status_code == 200
        fields = {name: re.search(f'name="{name}" value="([^"]+)"', consent.text).group(1)
                  for name in ("ticket", "csrf")}
        approval = await http.post(issuer + "/consent", data={**fields, "decision": "allow",
            "password": config["OAUTH_PASSWORD"]}, headers={"Origin": issuer})
        assert approval.status_code == 302
        redirect = urlsplit(approval.headers["location"])
        assert redirect.scheme + "://" + redirect.netloc + redirect.path == CALLBACK
        query = parse_qs(redirect.query)
        assert query["state"] == ["oauth-check"]
        exchange = dict(grant_type="authorization_code", client_id=client_id, code=query["code"][0],
                        code_verifier=verifier, redirect_uri=CALLBACK, resource=url)
        token_response = await http.post(issuer + "/token", data=exchange)
        assert token_response.status_code == 200
        tokens = token_response.json()
        assert (await http.post(issuer + "/token", data=exchange)).status_code == 400
        async with httpx2.AsyncClient(headers={"Authorization": "Bearer " + tokens["access_token"]}) as authenticated:
            async with Client(streamable_http_client(url, http_client=authenticated)) as client:
                tools = await client.list_tools()
                assert len(tools.tools) == 8
                result = await client.call_tool("list_files", {"path": "claude-test"})
                assert not result.is_error
        refresh = dict(grant_type="refresh_token", client_id=client_id, refresh_token=tokens["refresh_token"])
        rotated = await http.post(issuer + "/token", data=refresh)
        assert rotated.status_code == 200
        assert rotated.json()["refresh_token"] != tokens["refresh_token"]
        assert (await http.post(issuer + "/token", data=refresh)).status_code == 400
        assert (await http.post(issuer + "/revoke", data={"client_id": client_id,
            "token": rotated.json()["refresh_token"]})).status_code == 200
        assert (await http.get(url, headers={"Authorization": "Bearer " + tokens["access_token"]})).status_code == 401
    report = {"checked_utc": datetime.now(timezone.utc).isoformat(), "https": issuer.startswith("https:"),
        "discovery": True, "dcr": True, "owner_consent": True, "pkce_exchange": True,
        "code_replay_rejected": True, "mcp_tools": 8, "oauth_list_files_ok": True,
        "refresh_rotation": True, "refresh_replay_rejected": True, "revocation": True,
        "claude_web_ui_test": "Pending human connection; this check uses the official Python MCP client."}
    output = json.dumps(report, indent=2)
    if len(sys.argv) > 1:
        Path(sys.argv[1]).write_text(output + "\n", encoding="utf-8")
    print(output)


if __name__ == "__main__":
    asyncio.run(main())
