"""Authenticated Streamable HTTP MCP endpoint; run with python server.py."""

import secrets
from typing import Annotated

import uvicorn
from mcp.server import MCPServer
from mcp.server.transport_security import TransportSecuritySettings
from mcp.types import ToolAnnotations
from pydantic import Field
from starlette.responses import JSONResponse

from config import WORKSPACE, settings
from tools import Files

PathArg = Annotated[str, Field(strict=True, min_length=1, max_length=240)]


def create_app():
    token, _, public_host = settings()
    files = Files(WORKSPACE)
    mcp = MCPServer("Simple MCP File Server", version="1.0.0",
                    instructions="Work only in workspace. Read before editing. Keep outputs small. "
                    "Read PROJECT_STATE.md and CHECKPOINTS.md when resuming; run one writer at a time.")

    @mcp.tool(annotations=ToolAnnotations(read_only_hint=True, destructive_hint=False, open_world_hint=False))
    def list_files(path: PathArg = ".", limit: Annotated[int, Field(strict=True, ge=1, le=100)] = 100) -> dict:
        """List one workspace directory, up to limit entries. Hidden/unsupported files are excluded; check truncated."""
        return files.list_files(path, limit)

    hosts = ["127.0.0.1", "127.0.0.1:*", "localhost", "localhost:*"]
    origins = ["http://localhost:*", "http://127.0.0.1:*"]
    if public_host:
        hosts += [public_host, public_host + ":443"]
        origins.append("https://" + public_host)
    app = mcp.streamable_http_app(json_response=True, stateless_http=True,
        max_request_body_size=1024 * 1024,
        transport_security=TransportSecuritySettings(allowed_hosts=hosts, allowed_origins=origins))

    # A shared classroom secret, not an OAuth identity/authorization service.
    class BearerAuth:
        def __init__(self, app):
            self.app = app

        async def __call__(self, scope, receive, send):
            if scope["type"] == "http":
                headers = dict(scope["headers"])
                supplied = headers.get(b"authorization", b"")
                expected = ("Bearer " + token).encode()
                if not secrets.compare_digest(supplied, expected):
                    response = JSONResponse({"error": "Valid bearer token required."}, status_code=401,
                                            headers={"WWW-Authenticate": "Bearer"})
                    return await response(scope, receive, send)
            await self.app(scope, receive, send)

    return BearerAuth(app)


if __name__ == "__main__":
    _, port, _ = settings()
    uvicorn.run(create_app(), host="127.0.0.1", port=port, log_level="warning")
