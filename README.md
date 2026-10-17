# Simple MCP File Server

A small Python project for CSE2 Midterms Part 1. An AI client can manage text files inside `workspace/` and continue a task in a new session using saved handoff notes.

The server runs on your PC. For ordinary development, connect to `http://127.0.0.1:8765/mcp`. A temporary HTTPS tunnel is used for the assignment's deployment requirement; cloud hosting is unnecessary.

## Requirements

- Windows with Python **3.12 or newer** (tested on 3.12.14).
- Node.js **22.19 or newer**, npm, and Git.
- Codex CLI signed in with `codex login`, for the genuine agent demonstration.
- Cloudflare's `cloudflared` executable for the temporary HTTPS demonstration only.

Python 3.12 is required because the sandbox checks Windows junctions with `Path.is_junction`. No model API key is needed by this server. Codex uses the account you sign in with.

## Setup in PowerShell

```powershell
git clone https://github.com/zekurou1/cse2-midterms-mcp.git
cd cse2-midterms-mcp
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
npm.cmd ci
Copy-Item .env.example .env
.\.venv\Scripts\python.exe -c "from dotenv import set_key; import secrets; set_key('.env', 'MCP_TOKEN', secrets.token_urlsafe(32))"
npm.cmd start
```

If Python 3.12 is not installed, install it first or replace `py -3.12` with your Python 3.13/3.14 executable. The private repository requires access from its owner before cloning.

The generated `.env` stays on your machine. Never commit or share it. PM2 runs the server in the background and restarts it after process failure. Logs are in `.local/`. This setup does not install a Windows startup service.

```powershell
npm.cmd run status
.\.venv\Scripts\python.exe scripts/check_endpoint.py
.\.venv\Scripts\python.exe -m pytest -q
```

Stop only this project with `npm.cmd stop`; do not use `pm2 kill` or `pm2 stop all` when other projects are running.

## Eight tools

| Tool | Purpose | Important rule |
| --- | --- | --- |
| `list_files` | List one directory | Up to 100 visible permitted entries; reports truncation |
| `read_file` | Read numbered lines | Up to 100 lines and 16 KiB of returned text |
| `write_file` | Create or explicitly replace a file | Existing files require `overwrite=true` |
| `str_replace` | Replace an exact text passage | Exactly one nonempty match |
| `delete_file` | Delete one file | `confirm=true`; cannot delete directories/handoff records |
| `search_files` | Search literal text | Case sensitive; up to 200 readable files and 50 matches |
| `append_file` | Add text to an existing file | Preserves existing content; total size must fit |
| `file_info` | Return size and modification time | Only permitted workspace text files |

Paths are relative to `workspace/`. Supported extensions: `.md`, `.txt`, `.json`, `.csv`. Maximum file size: 256 KiB. Parent directories for new files are created inside the sandbox. Invalid inputs and file errors return useful MCP errors rather than raw stack traces.

`server.py` registers tools and handles HTTP authentication, schema enforcement and audit logging. `tools.py` contains the shared path checks and file operations. `config.py` contains the limits and environment settings. `oauth.py` adds optional owner-approved OAuth for Claude Web using the MCP SDK's protocol handlers.

## Connect Codex

See `examples/codex-config.toml`. The token comes from the `MCP_TOKEN` environment variable rather than a committed configuration value. Keep the default approval mode set to `prompt` for interactive use, especially overwrites, replacements and deletion.

The included demo runner supplies configuration only to that invocation and does not edit your global Codex settings:

```powershell
.\.venv\Scripts\python.exe scripts/run_demo.py planner
# Inspect the handoff before starting a fresh Writer session.
.\.venv\Scripts\python.exe scripts/run_demo.py writer
```

The runner disables shell tools, uses a separate read-only client working directory, ignores unrelated user MCP configuration and restricts available MCP tools per role. Planner: list/read/search/write/append. Writer: those five plus replace/info. Neither role receives deletion. Client allowlists are workflow controls, not separate server-side user accounts.

The two invocations start independent conversations. The Writer receives its goal and must recover the plan from files, without the Planner's conversation history. Calls run against the actual MCP endpoint; these are not scripted tool responses.

The repository includes the completed original run. For another rehearsal, use a fresh clone's workspace or deliberately restore the initial demo files from the setup commit after preserving any work you need. The runner does not silently reset or delete your files. Re-running also replaces the two transcript output files, so preserve evidence first.

## Handoff and evidence

- `PROJECT_STATE.md`: goal, status, sources and next action.
- `PLAN_LOG.md`: planned steps and actual progress.
- `CHECKPOINTS.md`: completed work and where the next session resumes.
- `DECISIONS.md`: choices and reasons.

All four live inside `workspace/`. Append historical progress to the logs; keep the current state at the top of `PROJECT_STATE.md` accurate.

`evidence/planner-session.jsonl` and `writer-session.jsonl` contain actual Codex events, tool arguments and results. `handoff-after-planner/` preserves the intermediate handoff. `demo-transcript.md` is a readable index/extract, and `validation.md` explains results and limits. Server audit logs in `.local/tool-calls.jsonl` are outside the exposed workspace. They contain the actual bounded text arguments/results for this synthetic demo; do not use private data in a submission run.

Verify all eight tools with MCP Inspector:

```powershell
.\.venv\Scripts\python.exe scripts/verify_inspector.py
npm.cmd run inspector
```

For the Inspector web UI, select Streamable HTTP and the local endpoint, then add an `Authorization: Bearer YOUR_LOCAL_SECRET` header. Use your generated secret privately. The executable script runs the Inspector CLI against all eight tools and writes its genuine responses to `evidence/inspector-checks.json`.

## Temporary HTTPS demonstration

The assignment permits Cloudflare Tunnel as an alternative to ngrok. A Cloudflare Quick Tunnel needs no account. It is temporary and has no uptime guarantee; its URL changes when restarted. The server uses ordinary JSON HTTP responses rather than SSE, which Quick Tunnels do not support.

Download `cloudflared-windows-amd64.exe` from the [official release page](https://github.com/cloudflare/cloudflared/releases), verify the release checksum/signature, and place it at `.local/bin/cloudflared.exe`. Then:

```powershell
npm.cmd run tunnel
Get-Content .local/tunnel-error.log -Tail 60
```

Find the current `https://....trycloudflare.com` URL in that log and append `/mcp`:

```powershell
.\.venv\Scripts\python.exe scripts/check_endpoint.py https://YOUR-CURRENT-HOST.trycloudflare.com/mcp
.\.venv\Scripts\python.exe scripts/run_demo.py planner --url https://YOUR-CURRENT-HOST.trycloudflare.com/mcp
.\.venv\Scripts\python.exe scripts/run_demo.py writer --url https://YOUR-CURRENT-HOST.trycloudflare.com/mcp
npm.cmd run stop:tunnel
```

The tunnel configuration forwards the Host header as `127.0.0.1:8765`, preserving the SDK's local Host validation. Authentication applies to every MCP request; optional OAuth discovery and sign-in endpoints are public. Browser MCP requests with unexpected Origins are rejected. `PUBLIC_HOST` in `.env` is available if using another tunnel without that Host override. If changing the port, also change the tunnel target and Host override in `ecosystem.config.cjs`.

Wait until the generated hostname resolves and `check_endpoint.py` passes before starting agents. A newly generated hostname failed to resolve through the local resolver during the restart test even though public DNS knew it; this is recorded as a tunnel limitation. Use localhost while developing and verify the current public URL before the live demonstration.

## Quick Claude Web test without sign-in

For a temporary test with synthetic files only, set `MCP_DEMO_NO_AUTH=1` in ignored `.env`, then restart `cse2-mcp`. Add the current HTTPS `/mcp` URL in Claude and select **No sign-in** and **Streamable HTTP**. Enable the connector in a new chat and ask it to list available files.

In this mode, all eight tools are rooted at `workspace/claude-test/`, so paths such as `notes/mcp-basics.md` are relative to that folder. OAuth is disabled. Anyone with the public URL can read and modify these test files while the tunnel is running. The main workspace, server source, secrets and logs remain outside this tool sandbox.

Run `python scripts/check_demo.py https://YOUR-CURRENT-HOST.trycloudflare.com/mcp` to exercise all eight tools without credentials. Restore `MCP_DEMO_NO_AUTH=0` and restart when finished, or stop the tunnel. Authentication is enabled by default; do not use no-sign-in mode for private files or the authenticated security demonstration.

## Connect Claude Web with OAuth

Claude's static request-header credentials are a limited organization beta. For an account without that feature, use the optional single-owner OAuth flow. No Google account, paid identity provider or database is needed.

With the server and current tunnel running:

```powershell
.\.venv\Scripts\python.exe scripts/enable_claude.py https://YOUR-CURRENT-HOST.trycloudflare.com/mcp
.\node_modules\.bin\pm2.cmd restart cse2-mcp
.\.venv\Scripts\python.exe scripts/check_oauth.py
```

This sets `OAUTH_ISSUER_URL` and a separate random `OAUTH_PASSWORD` in ignored `.env`. The private password is also saved in ignored `.local/oauth-login-code.txt`. Never paste it into chat or commit it. Read it locally when the server's authorization page asks for it.

1. In Claude, remove the failed connector if one already exists, then add the current HTTPS URL ending in `/mcp`.
2. Select **Sign in now**, **Register automatically**, and **Streamable HTTP**. Do not choose No sign-in or enter the bearer secret as an OAuth client secret.
3. On **Connect CSE2 File Server**, enter the local connection password and select **Allow Claude**. Approval grants access to all eight tools in the sandbox. The return address must be `claude.ai`.
4. Confirm the connector shows Connected and eight tools. In a new chat, enable it under **+ > Connectors**. Ask: `Use CSE2 File Server to list the files in claude-test.`

The SDK handles DCR, S256 PKCE, redirect validation and token exchange. Owner consent checks a separate password, CSRF cookie and Origin, with five failed attempts per minute. Only Claude Web's exact callback is registered. Codes last two minutes, access tokens one hour, and rotating refresh tokens one day. Discovery and sign-in routes are public; `/mcp` always requires the original bearer secret or an approved OAuth access token. Passwords and tokens are not accepted in URL query strings.

Registrations and grants are held in bounded process memory to keep the classroom project small. Restarting the server invalidates OAuth sessions; remove and re-add the Claude connector to register again. The original static bearer connection continues working. When the tunnel URL changes, run `enable_claude.py` with the new URL, restart the server and re-add the connector. Stop the tunnel after testing.

`tests/test_oauth.py` and `scripts/check_oauth.py` cover the auth flow; `evidence/oauth-checks.json` records a successful real HTTPS OAuth-authenticated MCP call using the Python client. This is not evidence that a human completed the Claude Web dialog.

References: [Claude authentication requirements](https://claude.com/docs/connectors/building/authentication), [Claude connector testing](https://claude.com/docs/connectors/building/testing).

## Security and limits

Every tool uses the same sandbox. Absolute/drive-relative/UNC paths, traversal, hidden paths, Windows device names and alternate data streams are rejected. Symlinks, junctions and hard-linked files are rejected. Complete-file writes use temporary files and replacement to reduce partial writes.

The bearer secret protects the classroom endpoint for local clients. Optional OAuth grants provide Claude Web access after owner approval; there is no per-user access system. Flags such as `confirm=true` and MCP annotations do not prove approval of each file operation: use the client's confirmation controls, and keep deletion disabled for normal agents. The automated fixture run creates/appends demo files under the user's project authorization; it does not prove that a human clicked an interactive approval dialog.

Use one writer at a time. The project does not protect against a hostile local user racing filesystem changes, provide version locking, rotate audit logs, or guarantee service after Windows reboot. Keep the PC awake for a live demonstration and stop the tunnel afterwards.

## Submission and live presentation

The two submission outputs are this repository and the linked documentation report. The transcript, logs, handoff snapshots and tests are repository contents, not separate submission outputs. The brief also requires a five-minute live demonstration.

Suggested timing: purpose/design (45 seconds), tools/security (60 seconds), Planner/Writer handoff (150 seconds), evidence/tradeoffs (45 seconds). Explain that the project demonstrates shared file context across sessions; the AI reasoning stays in Codex.

Documentation: [CSE2 Midterms MCP File Server Documentation](https://docs.google.com/document/d/1WttPP1LkViTinown0QSDgeAHH-k4NGNCwqEKVfWx7eA/edit). Both submission links are also recorded in `evidence/deliverables.json`. Access is private until the owner shares it with the evaluator.

References: [Python SDK](https://py.sdk.modelcontextprotocol.io/), [MCP Inspector](https://modelcontextprotocol.io/docs/tools/inspector), [Codex MCP configuration](https://developers.openai.com/codex/mcp), [Cloudflare Quick Tunnels](https://developers.cloudflare.com/tunnel/get-started/quick-tunnels/), [PM2 process management](https://pm2.keymetrics.io/docs/usage/process-management/). The supplied lecture PDF's slides 16-20 define the project/rubric; the PDF itself is not redistributed here.
