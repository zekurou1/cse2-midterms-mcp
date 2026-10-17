"""Enable Claude Web OAuth for the current tunnel, without displaying secrets."""

import argparse
import secrets
import sys
from pathlib import Path

from dotenv import dotenv_values, set_key

BASE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE))
from config import oauth_settings


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("url", help="Current HTTPS tunnel URL, with or without /mcp")
    args = parser.parse_args()
    issuer = args.url.rstrip("/").removesuffix("/mcp")
    # Validate before writing anything. Reuse the owner password across tunnel restarts.
    import os
    password = dotenv_values(BASE / ".env").get("OAUTH_PASSWORD") or secrets.token_urlsafe(32)
    os.environ.update(OAUTH_ISSUER_URL=issuer, OAUTH_PASSWORD=password)
    oauth_settings()
    set_key(BASE / ".env", "OAUTH_ISSUER_URL", issuer)
    set_key(BASE / ".env", "OAUTH_PASSWORD", password)
    local = BASE / ".local"
    local.mkdir(exist_ok=True)
    (local / "oauth-login-code.txt").write_text(password + "\n", encoding="utf-8")
    print("OAuth configured for " + issuer + "/mcp")
    print("Private connection password: .local/oauth-login-code.txt (do not commit/share)")
    print("Restart: .\\node_modules\\.bin\\pm2.cmd restart cse2-mcp")
