"""Exercise all eight tools over HTTPS without credentials, using one temporary file."""

import asyncio
import json
import secrets
import sys
from datetime import datetime, timezone
from pathlib import Path

from mcp import Client
from mcp.client.streamable_http import streamable_http_client


async def main(url):
    path = "connection-check-" + secrets.token_hex(6) + ".txt"
    calls = [
        ("list_files", {"path": "."}),
        ("write_file", {"path": path, "content": "test start\n"}),
        ("read_file", {"path": path}),
        ("str_replace", {"path": path, "old_str": "start", "new_str": "updated"}),
        ("append_file", {"path": path, "content": "test end\n"}),
        ("search_files", {"query": "test updated"}),
        ("file_info", {"path": path}),
        ("delete_file", {"path": path, "confirm": True}),
    ]
    async with Client(streamable_http_client(url)) as client:
        assert len((await client.list_tools()).tools) == 8
        for name, arguments in calls:
            result = await client.call_tool(name, arguments)
            assert not result.is_error, name
        assert (await client.call_tool("read_file", {"path": "../PROJECT_STATE.md"})).is_error
    report = {"checked_utc": datetime.now(timezone.utc).isoformat(), "https": url.startswith("https:"),
              "authentication_sent": False, "successful_tools": [name for name, _ in calls],
              "parent_escape_rejected": True, "temporary_file_deleted": True,
              "claude_web_ui_test": "Pending; this check uses the official Python MCP client."}
    output = json.dumps(report, indent=2)
    (Path(__file__).resolve().parents[1] / "evidence/demo-no-auth-checks.json").write_text(output + "\n", encoding="utf-8")
    print(output)


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1]))
