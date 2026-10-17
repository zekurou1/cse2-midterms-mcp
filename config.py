"""Small environment configuration. The exposed folder is always workspace/."""

import os
from urllib.parse import urlsplit
from pathlib import Path

from dotenv import load_dotenv

BASE = Path(__file__).resolve().parent
WORKSPACE = BASE / "workspace"
AUDIT_LOG = BASE / ".local" / "tool-calls.jsonl"
MAX_BYTES = 256 * 1024
EXTENSIONS = {".md", ".txt", ".json", ".csv"}
HANDOFF = {"project_state.md", "plan_log.md", "checkpoints.md", "decisions.md"}


def settings():
    load_dotenv(BASE / ".env")
    token = os.environ.get("MCP_TOKEN", "")
    if len(token) < 32 or token.startswith("REPLACE_"):
        raise ValueError("Set MCP_TOKEN to a random secret of at least 32 characters.")
    host = os.environ.get("PUBLIC_HOST", "").strip()
    if host and (not all(c.isalnum() or c in ".-" for c in host) or "." not in host):
        raise ValueError("PUBLIC_HOST must be a hostname, without a URL scheme or path.")
    port = int(os.environ.get("MCP_PORT", "8765"))
    if not 1024 <= port <= 65535:
        raise ValueError("MCP_PORT must be between 1024 and 65535.")
    return token, port, host


def oauth_settings():
    """Disabled unless a fixed, public issuer origin and owner password are configured."""
    issuer = os.environ.get("OAUTH_ISSUER_URL", "").strip().rstrip("/")
    password = os.environ.get("OAUTH_PASSWORD", "")
    if not issuer:
        return None
    parsed = urlsplit(issuer)
    if (parsed.scheme != "https" or not parsed.hostname or parsed.path or parsed.query
            or parsed.fragment or parsed.username or parsed.password):
        raise ValueError("OAUTH_ISSUER_URL must be the HTTPS tunnel origin without /mcp.")
    if len(password) < 32:
        raise ValueError("Set a separate OAUTH_PASSWORD of at least 32 characters.")
    return issuer, password


def demo_no_auth():
    """Explicit temporary testing opt-in; the server restricts it to claude-test/."""
    return os.environ.get("MCP_DEMO_NO_AUTH", "0") == "1"
