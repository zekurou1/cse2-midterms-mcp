"""Authenticated Streamable HTTP MCP endpoint; run with python server.py."""

import secrets
import json
from contextvars import ContextVar
from datetime import datetime, timezone
from typing import Annotated

import uvicorn
from mcp.server import MCPServer
from mcp.server.transport_security import TransportSecuritySettings
from mcp.types import CallToolResult, TextContent, ToolAnnotations
from jsonschema import validate, ValidationError
from pydantic import Field
from starlette.responses import JSONResponse

from config import AUDIT_LOG, WORKSPACE, demo_no_auth, oauth_settings, settings
from oauth import OwnerOAuth
from tools import Files
from mcp.server.mcpserver.exceptions import ToolError

PathArg = Annotated[str, Field(strict=True, min_length=1, max_length=240)]
Content = Annotated[str, Field(strict=True, max_length=262144)]
Flag = Annotated[bool, Field(strict=True)]
SESSION = ContextVar("demo_session", default="unlabeled")
READ = ToolAnnotations(read_only_hint=True, destructive_hint=False, open_world_hint=False)
WRITE = ToolAnnotations(read_only_hint=False, destructive_hint=True, open_world_hint=False)


def create_app():
    token, _, public_host = settings()
    demo = demo_no_auth()
    oauth_config = None if demo else oauth_settings()
    oauth = OwnerOAuth(*oauth_config) if oauth_config else None
    oauth_app = oauth.app() if oauth else None
    files = Files(WORKSPACE / "claude-test" if demo else WORKSPACE)

    async def observe(ctx, call_next):
        if ctx.method == "tools/list":
            result = await call_next(ctx)
            for tool in result["tools"]:
                tool["inputSchema"]["additionalProperties"] = False
            return result
        if ctx.method != "tools/call":
            return await call_next(ctx)
        params = ctx.params or {}
        name = params.get("name", "")
        args = params.get("arguments", {})
        result = None
        try:
            schema = next((t.input_schema for t in await mcp.list_tools() if t.name == name), None)
            if schema:
                validate(args, {**schema, "additionalProperties": False})
            result = await call_next(ctx)
            return result
        except ValidationError as error:
            result = CallToolResult(is_error=True, content=[TextContent(type="text", text="Invalid tool arguments: " + error.message[:300])])
            return result
        finally:
            # Actual calls, including invalid inputs; audit data is not agent-editable.
            record = {"time_utc": datetime.now(timezone.utc).isoformat(), "session": SESSION.get(),
                      "request_id": str(ctx.request_id), "tool": name, "arguments": args,
                      "result": result.model_dump(mode="json", by_alias=True) if hasattr(result, "model_dump") else result}
            line = json.dumps(record, ensure_ascii=True).replace(token, "[REDACTED]")
            if oauth:
                line = line.replace(oauth.password, "[REDACTED]")
            AUDIT_LOG.parent.mkdir(exist_ok=True)
            with AUDIT_LOG.open("a", encoding="utf-8") as stream:
                stream.write(line + "\n")

    mcp = MCPServer("Simple MCP File Server", version="1.0.0",
                    instructions="Work only in workspace. Read before editing. Keep outputs small. "
                    "Read PROJECT_STATE.md and CHECKPOINTS.md when resuming; run one writer at a time.",
                    middleware=[observe])

    def operate(name, **args):
        try:
            return getattr(files, name)(**args)
        except OSError:
            raise ToolError("File operation failed. Check the relative path, file type and permissions.") from None

    @mcp.tool(annotations=READ)
    def list_files(path: PathArg = ".", limit: Annotated[int, Field(strict=True, ge=1, le=100)] = 100) -> dict:
        """List one workspace directory, up to limit entries. Hidden/unsupported files are excluded; check truncated."""
        return operate("list_files", path=path, limit=limit)

    @mcp.tool(annotations=READ)
    def read_file(path: PathArg, start_line: Annotated[int, Field(strict=True, ge=1)] = 1,
                  max_lines: Annotated[int, Field(strict=True, ge=1, le=100)] = 100) -> dict:
        """Read numbered UTF-8 lines, at most 100 lines/16 KiB. Use next_line to continue. Missing/binary files fail."""
        return operate("read_file", path=path, start_line=start_line, max_lines=max_lines)

    @mcp.tool(annotations=WRITE)
    def write_file(path: PathArg, content: Content, overwrite: Flag = False) -> dict:
        """Create a UTF-8 file (256 KiB maximum). Existing files require prior reading, human approval and overwrite=true."""
        return operate("write_file", path=path, content=content, overwrite=overwrite)

    @mcp.tool(annotations=WRITE)
    def str_replace(path: PathArg, old_str: Annotated[str, Field(strict=True, min_length=1, max_length=262144)],
                    new_str: Content) -> dict:
        """Replace one exact nonempty match in a text file. Read first; zero/multiple matches fail. Approve edits in client."""
        return operate("str_replace", path=path, old_str=old_str, new_str=new_str)

    @mcp.tool(annotations=WRITE)
    def delete_file(path: PathArg, confirm: Flag = False) -> dict:
        """Delete one UTF-8 file after human approval and confirm=true. Directories and handoff records cannot be deleted."""
        return operate("delete_file", path=path, confirm=confirm)

    @mcp.tool(annotations=READ)
    def search_files(query: Annotated[str, Field(strict=True, min_length=1, max_length=200)],
                     path: PathArg = ".", max_results: Annotated[int, Field(strict=True, ge=1, le=50)] = 50) -> dict:
        """Search literal case-sensitive text, scanning at most 200 permitted files. Returns snippets; check truncated."""
        return operate("search_files", query=query, path=path, max_results=max_results)

    @mcp.tool(annotations=ToolAnnotations(read_only_hint=False, destructive_hint=False, open_world_hint=False))
    def append_file(path: PathArg, content: Content) -> dict:
        """Append UTF-8 text to an existing file, preserving prior entries. Resulting file must fit 256 KiB."""
        return operate("append_file", path=path, content=content)

    @mcp.tool(annotations=READ)
    def file_info(path: PathArg) -> dict:
        """Report byte size and UTC modification time of a permitted UTF-8 file; missing/binary/oversized files fail."""
        return operate("file_info", path=path)

    hosts = ["127.0.0.1", "127.0.0.1:*", "localhost", "localhost:*"]
    origins = ["http://localhost:*", "http://127.0.0.1:*"]
    if public_host:
        hosts += [public_host, public_host + ":443"]
        origins.append("https://" + public_host)
    app = mcp.streamable_http_app(json_response=True, stateless_http=True,
        max_request_body_size=1024 * 1024,
        transport_security=TransportSecuritySettings(allowed_hosts=hosts, allowed_origins=origins))

    # Keep the original local-client secret; optionally accept owner-approved OAuth grants.
    class BearerAuth:
        def __init__(self, app):
            self.app = app

        async def __call__(self, scope, receive, send):
            if scope["type"] == "http":
                if oauth_app and scope["path"] != "/mcp":
                    return await oauth_app(scope, receive, send)
                headers = dict(scope["headers"])
                supplied = headers.get(b"authorization", b"")
                expected = ("Bearer " + token).encode()
                authorized = demo or secrets.compare_digest(supplied, expected)
                if not authorized and oauth and supplied.startswith(b"Bearer "):
                    grant = await oauth.load_access_token(supplied[7:].decode("ascii", errors="ignore"))
                    authorized = bool(grant and grant.resource == oauth.resource and "files" in grant.scopes)
                if not authorized:
                    challenge = "Bearer"
                    if oauth:
                        challenge += f' resource_metadata="{oauth.issuer}/.well-known/oauth-protected-resource/mcp", scope="files"'
                    response = JSONResponse({"error": "Valid bearer token required."}, status_code=401,
                                            headers={"WWW-Authenticate": challenge})
                    return await response(scope, receive, send)
                label = headers.get(b"x-demo-session", b"unlabeled").decode("ascii", errors="ignore")[:64]
                marker = SESSION.set(label)
                try:
                    return await self.app(scope, receive, send)
                finally:
                    SESSION.reset(marker)
            await self.app(scope, receive, send)

    return BearerAuth(app)


if __name__ == "__main__":
    _, port, _ = settings()
    uvicorn.run(create_app(), host="127.0.0.1", port=port, log_level="warning")
