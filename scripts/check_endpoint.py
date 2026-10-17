"""Check a running local or HTTPS endpoint; emits results without the secret."""

import asyncio
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import httpx2
from dotenv import dotenv_values
from mcp import Client
from mcp.client.streamable_http import streamable_http_client

BASE = Path(__file__).resolve().parents[1]


async def check(url):
    token = dotenv_values(BASE / ".env")["MCP_TOKEN"]
    checks = {"checked_utc": datetime.now(timezone.utc).isoformat(), "url": url}
    async with httpx2.AsyncClient(timeout=30) as http:
        checks["missing_token_status"] = (await http.get(url)).status_code
        checks["wrong_token_status"] = (await http.get(url, headers={"Authorization": "Bearer incorrect"})).status_code
    async with httpx2.AsyncClient(headers={"Authorization": "Bearer " + token}, timeout=30) as http:
        async with Client(streamable_http_client(url, http_client=http)) as client:
            tools = await client.list_tools()
            checks["tools"] = [tool.name for tool in tools.tools]
            checks["strict_schemas"] = all(t.input_schema.get("additionalProperties") is False for t in tools.tools)
            result = await client.call_tool("list_files", {"path": "notes"})
            checks["authenticated_list_ok"] = not result.is_error
    assert checks["missing_token_status"] == checks["wrong_token_status"] == 401
    assert len(checks["tools"]) == 8 and checks["strict_schemas"] and checks["authenticated_list_ok"]
    print(json.dumps(checks, indent=2))


if __name__ == "__main__":
    asyncio.run(check(sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8765/mcp"))
