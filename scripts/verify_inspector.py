"""Run all eight real tool calls through the installed MCP Inspector CLI."""

import json
import shutil
import subprocess
import uuid
from pathlib import Path

from dotenv import dotenv_values

BASE = Path(__file__).resolve().parents[1]
token = dotenv_values(BASE / ".env")["MCP_TOKEN"]
launcher = BASE / "node_modules/@modelcontextprotocol/inspector/clients/launcher/build/index.js"
target = "inspector-" + uuid.uuid4().hex[:8] + ".txt"
cases = [
    ("list_files", {"path": "."}),
    ("write_file", {"path": target, "content": "first\nsecond\n"}),
    ("read_file", {"path": target}),
    ("str_replace", {"path": target, "old_str": "second", "new_str": "updated"}),
    ("append_file", {"path": target, "content": "last\n"}),
    ("search_files", {"query": "updated"}),
    ("file_info", {"path": target}),
    ("delete_file", {"path": target, "confirm": True}),
]
records = []
for name, arguments in cases:
    command = [shutil.which("node"), str(launcher), "--cli", "http://127.0.0.1:8765/mcp",
               "--method", "tools/call", "--tool-name", name, "--tool-args-json", json.dumps(arguments),
               "--format", "json", "--header", "Authorization: Bearer " + token, "X-Demo-Session: inspector"]
    result = subprocess.run(command, capture_output=True, text=True, timeout=40)
    if result.returncode:
        raise RuntimeError(f"Inspector failed for {name}: " + result.stderr.replace(token, "[REDACTED]"))
    payload = json.loads(result.stdout)
    assert not payload.get("result", payload).get("isError", False), payload
    records.append({"tool": name, "arguments": arguments, "inspector_output": payload})
out = BASE / "evidence/inspector-checks.json"
out.write_text(json.dumps(records, indent=2), encoding="utf-8")
print(f"Inspector successfully exercised {len(records)} tools; evidence saved.")
