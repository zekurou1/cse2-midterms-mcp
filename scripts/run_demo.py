"""Run ONE real Codex session; run planner first, then writer as a fresh invocation."""

import argparse
import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from dotenv import dotenv_values

BASE = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("role", choices=["planner", "writer"])
parser.add_argument("--url", default="http://127.0.0.1:8765/mcp")
args = parser.parse_args()
token = dotenv_values(BASE / ".env")["MCP_TOKEN"]
allowed = ["list_files", "read_file", "search_files", "write_file", "append_file"]
if args.role == "writer":
    allowed += ["str_replace", "file_info"]
cwd = tempfile.mkdtemp(prefix="cse2-demo-client-")
prompt = (BASE / f"examples/{args.role}.txt").read_text(encoding="utf-8")
command = [shutil.which("codex"), "exec", "--ignore-user-config", "--disable", "shell_tool",
           "--skip-git-repo-check", "--ephemeral", "--json", "--sandbox", "read-only", "-C", cwd]
overrides = {
    "mcp_servers.midterms.url": args.url,
    "mcp_servers.midterms.bearer_token_env_var": "MCP_TOKEN",
    "mcp_servers.midterms.enabled_tools": allowed,
    "mcp_servers.midterms.http_headers": {"X-Demo-Session": args.role},
    "mcp_servers.midterms.required": True,
}
for key, value in overrides.items():
    # JSON strings/arrays/bools also parse as TOML values; inline tables use TOML syntax.
    encoded = '{ "X-Demo-Session" = ' + json.dumps(args.role) + ' }' if isinstance(value, dict) else json.dumps(value)
    command += ["-c", key + "=" + encoded]
command.append("-")
evidence = BASE / "evidence"
evidence.mkdir(exist_ok=True)
with (evidence / f"{args.role}-session.jsonl").open("w", encoding="utf-8") as out:
    result = subprocess.run(command, input=prompt, text=True, encoding="utf-8", stdout=out,
                            stderr=subprocess.PIPE, env={**os.environ, "MCP_TOKEN": token}, timeout=360)
(BASE / f".local/{args.role}-stderr.log").write_text(result.stderr.replace(token, "[REDACTED]"), encoding="utf-8")
if result.returncode:
    raise SystemExit(f"Codex exited {result.returncode}. Inspect .local/{args.role}-stderr.log.")
events = [json.loads(line) for line in (evidence / f"{args.role}-session.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
calls = [e["item"] for e in events if e.get("type") == "item.completed" and e.get("item", {}).get("type") == "mcp_tool_call"]
assert calls and all(c["server"] == "midterms" and c["tool"] in allowed for c in calls)
assert len(calls) <= 25, "Call budget exceeded; inspect the genuine transcript before rerunning."
assert any(e.get("type") == "turn.completed" for e in events), "No completed Codex turn"
print(f"{args.role}: {len(calls)} actual MCP calls recorded. Review the transcript and workspace before the next session.")
