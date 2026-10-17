"""Real SDK OAuth handlers: consent, PKCE, replay, refresh and grant boundaries."""

import asyncio
import base64
import hashlib
import re
import time
from urllib.parse import parse_qs, urlsplit

from starlette.testclient import TestClient
import pytest

from oauth import CALLBACK, OwnerOAuth

ISSUER = "https://classroom.example"
PASSWORD = "local-owner-password-" + "x" * 32


@pytest.fixture
def oauth():
    provider = OwnerOAuth(ISSUER, PASSWORD)
    with TestClient(provider.app(), base_url=ISSUER, follow_redirects=False) as client:
        yield provider, client


def register(client, callback=CALLBACK):
    return client.post("/register", json={"redirect_uris": [callback],
        "token_endpoint_auth_method": "none", "grant_types": ["authorization_code", "refresh_token"],
        "response_types": ["code"], "scope": "files offline_access"})


def approval(client, client_id, **overrides):
    verifier = "v" * 64
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip("=")
    params = dict(client_id=client_id, response_type="code", redirect_uri=CALLBACK, state="original-state",
                  scope="files offline_access", code_challenge=challenge, code_challenge_method="S256",
                  resource=ISSUER + "/mcp")
    response = client.get("/authorize", params={**params, **overrides})
    assert response.status_code == 302
    page = client.get(response.headers["location"])
    assert page.status_code == 200
    assert page.headers["Referrer-Policy"] == "same-origin"
    fields = {name: re.search(f'name="{name}" value="([^"]+)"', page.text).group(1)
              for name in ("ticket", "csrf")}
    return fields, verifier


def grant(client):
    registration = register(client)
    assert registration.status_code == 201
    client_id = registration.json()["client_id"]
    fields, verifier = approval(client, client_id)
    result = client.post("/consent", data={**fields, "password": PASSWORD, "decision": "allow"},
                         headers={"Origin": ISSUER})
    assert result.status_code == 302
    assert result.headers["Referrer-Policy"] == "no-referrer"
    query = parse_qs(urlsplit(result.headers["location"]).query)
    assert query["state"] == ["original-state"]
    return dict(grant_type="authorization_code", code=query["code"][0], client_id=client_id,
                redirect_uri=CALLBACK, code_verifier=verifier, resource=ISSUER + "/mcp")


def test_discovery_and_redirect_restriction(oauth):
    _, client = oauth
    metadata = client.get("/.well-known/oauth-authorization-server").json()
    assert metadata["code_challenge_methods_supported"] == ["S256"]
    assert "none" in metadata["token_endpoint_auth_methods_supported"]
    resource = client.get("/.well-known/oauth-protected-resource/mcp").json()
    assert resource["resource"] == ISSUER + "/mcp"
    assert register(client, "https://evil.example/callback").status_code == 400


def test_consent_rejects_missing_password_csrf_and_origin(oauth):
    provider, client = oauth
    client_id = register(client).json()["client_id"]
    fields, _ = approval(client, client_id)
    for data, origin, status in [({**fields, "password": "wrong"}, ISSUER, 403),
                               ({**fields, "password": PASSWORD}, "https://evil.example", 403),
                               ({**fields, "csrf": "wrong", "password": PASSWORD}, ISSUER, 400)]:
        assert client.post("/consent", data=data, headers={"Origin": origin}).status_code == status
    assert not provider.codes


def test_code_pkce_replay_refresh_and_revoke(oauth):
    provider, client = oauth
    exchange = grant(client)
    assert client.post("/token", data={**exchange, "resource": "https://evil.example/mcp"}).json()["error"] == "invalid_target"
    assert client.post("/token", data={**exchange, "code_verifier": "wrong"}).status_code == 400
    assert client.post("/token", data={**exchange, "redirect_uri": "https://evil.example"}).status_code == 400
    response = client.post("/token", data=exchange)
    assert response.status_code == 200, response.text
    tokens = response.json()
    access = asyncio.run(provider.load_access_token(tokens["access_token"]))
    assert access.resource == ISSUER + "/mcp" and access.subject == "owner"
    assert client.post("/token", data=exchange).json()["error"] == "invalid_grant"
    refresh = dict(grant_type="refresh_token", client_id=exchange["client_id"], refresh_token=tokens["refresh_token"])
    rotated = client.post("/token", data=refresh)
    assert rotated.status_code == 200
    assert rotated.json()["refresh_token"] != tokens["refresh_token"]
    assert client.post("/token", data=refresh).json()["error"] == "invalid_grant"
    assert client.post("/revoke", data={"client_id": exchange["client_id"], "token": rotated.json()["refresh_token"]}).status_code == 200
    assert not provider.access and not provider.refresh


def test_oauth_token_reaches_real_mcp_and_static_token_still_works(tmp_path, monkeypatch):
    import server
    monkeypatch.setattr(server, "demo_no_auth", lambda: False)
    monkeypatch.setattr(server, "settings", lambda: ("static-secret-" + "s" * 32, 8765, ""))
    monkeypatch.setattr(server, "oauth_settings", lambda: (ISSUER, PASSWORD))
    monkeypatch.setattr(server, "WORKSPACE", tmp_path / "workspace")
    monkeypatch.setattr(server, "AUDIT_LOG", tmp_path / "audit.jsonl")
    with TestClient(server.create_app(), base_url=ISSUER, follow_redirects=False) as client:
        unauthorized = client.get("/mcp")
        assert unauthorized.status_code == 401
        assert 'resource_metadata="' in unauthorized.headers["WWW-Authenticate"]
        tokens = client.post("/token", data=grant(client)).json()
        for token in (tokens["access_token"], "static-secret-" + "s" * 32):
            result = client.post("/mcp", json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"},
                headers={"Authorization": "Bearer " + token, "Accept": "application/json, text/event-stream",
                         "Host": "127.0.0.1:8765", "MCP-Protocol-Version": "2025-06-18"})
            assert result.status_code == 200, result.text
            assert len(result.json()["result"]["tools"]) == 8
        assert client.get("/.well-known/oauth-authorization-server", headers={"Host": "evil.example"}).status_code == 400


def test_no_auth_demo_is_confined_to_synthetic_folder(tmp_path, monkeypatch):
    import server
    monkeypatch.setattr(server, "settings", lambda: ("s" * 40, 8765, ""))
    monkeypatch.setattr(server, "demo_no_auth", lambda: True)
    monkeypatch.setattr(server, "oauth_settings", lambda: pytest.fail("OAuth must be disabled in demo mode"))
    monkeypatch.setattr(server, "WORKSPACE", tmp_path / "workspace")
    monkeypatch.setattr(server, "AUDIT_LOG", tmp_path / "audit.jsonl")
    root = tmp_path / "workspace"
    root.mkdir()
    (root / "outside.md").write_text("Not part of the public demo", encoding="utf-8")
    with TestClient(server.create_app(), base_url="http://127.0.0.1:8765") as client:
        def call(method, params=None):
            response = client.post("/mcp", json={"jsonrpc": "2.0", "id": 1, "method": method, "params": params or {}},
                headers={"Accept": "application/json, text/event-stream", "MCP-Protocol-Version": "2025-06-18"})
            assert response.status_code == 200
            return response.json()["result"]
        assert len(call("tools/list")["tools"]) == 8
        assert not call("tools/call", {"name": "write_file", "arguments": {"path": "test.md", "content": "demo"}}).get("isError")
        assert (root / "claude-test/test.md").read_text() == "demo"
        assert call("tools/call", {"name": "read_file", "arguments": {"path": "../outside.md"}})["isError"]
        assert client.get("/.well-known/oauth-authorization-server").status_code == 404


def test_expiry_and_wrong_client(oauth):
    provider, client = oauth
    exchange = grant(client)
    other = register(client).json()["client_id"]
    assert client.post("/token", data={**exchange, "client_id": other}).json()["error"] == "invalid_grant"
    provider.codes[exchange["code"]].expires_at = time.time() - 1
    assert client.post("/token", data=exchange).json()["error"] == "invalid_grant"


def test_wrong_resource_and_no_pkce(oauth):
    _, client = oauth
    client_id = register(client).json()["client_id"]
    params = dict(client_id=client_id, response_type="code", redirect_uri=CALLBACK,
                  code_challenge="x" * 43, code_challenge_method="S256", resource="https://evil.example/mcp")
    response = client.get("/authorize", params=params)
    assert "invalid_target" in response.headers["location"]
    del params["code_challenge"]
    assert "invalid_request" in client.get("/authorize", params=params).headers["location"]


def test_cancel_rate_limit_and_body_limit(oauth):
    provider, client = oauth
    client_id = register(client).json()["client_id"]
    fields, _ = approval(client, client_id)
    cancel = client.post("/consent", data={**fields, "decision": "deny"}, headers={"Origin": ISSUER})
    assert "access_denied" in cancel.headers["location"] and not provider.codes
    fields, _ = approval(client, client_id)
    for _ in range(5):
        assert client.post("/consent", data={**fields, "password": "bad"}, headers={"Origin": ISSUER}).status_code == 403
    assert client.post("/consent", data={**fields, "password": PASSWORD}, headers={"Origin": ISSUER}).status_code == 429
    assert client.post("/consent", content=b"x" * 20000).status_code == 413
