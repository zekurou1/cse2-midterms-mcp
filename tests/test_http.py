"""Exercise an actual server process and the official MCP client over HTTP."""

import asyncio
import json
import os
import secrets
import socket
import subprocess
import sys
import time
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import httpx2
import pytest
from mcp import Client
from mcp.client.streamable_http import streamable_http_client

BASE = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def endpoint():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    token = secrets.token_urlsafe(32)
    env = {**os.environ, "MCP_TOKEN": token, "MCP_PORT": str(port), "PUBLIC_HOST": ""}
    process = subprocess.Popen([sys.executable, "server.py"], cwd=BASE, env=env,
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    url = f"http://127.0.0.1:{port}/mcp"
    try:
        for _ in range(100):
            try:
                urlopen(url, timeout=0.2)
            except HTTPError:
                break
            except OSError:
                time.sleep(0.1)
        else:
            raise AssertionError("Server did not start")
        yield url, token
    finally:
        process.terminate()
        process.wait(timeout=10)


@pytest.mark.parametrize("headers", [{}, {"Authorization": "Bearer wrong"}])
def test_http_requires_auth(endpoint, headers):
    with pytest.raises(HTTPError) as error:
        urlopen(Request(endpoint[0], headers=headers), timeout=3)
    assert error.value.code == 401


def test_actual_mcp_client(endpoint):
    async def run():
        async with httpx2.AsyncClient(headers={"Authorization": "Bearer " + endpoint[1]}) as http:
            async with Client(streamable_http_client(endpoint[0], http_client=http)) as client:
                tools = await client.list_tools()
                assert any(t.name == "list_files" for t in tools.tools)
                result = await client.call_tool("list_files", {"path": ".", "limit": 5})
                assert not result.is_error
    asyncio.run(run())
