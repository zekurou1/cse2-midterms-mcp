# Implementation and verification record

Date: 2026-10-17, Asia/Manila. Scope: CSE2 Midterms Part 1.

## Observed results

| Check | Result | Evidence |
| --- | --- | --- |
| Original implementation Python tests | 24 passed, zero skipped; OAuth update below | tests/; clean-checkout.json |
| Fresh checkout | New venv, requirements installation, npm ci and 24 passing tests | clean-checkout.json |
| Tool discovery | Eight strict schemas; unknown arguments rejected | tool-schemas.json; HTTP tests |
| MCP Inspector | All eight tools called successfully; traversal returned isError | inspector-checks.json |
| HTTP authentication | Missing/wrong token returned 401; correct token allowed discovery/calls | https-checks.json |
| Host and Origin protection | Unexpected Host 421; unexpected Origin 403 | tests/test_http.py |
| Python process failure | PM2 replaced the terminated listening process; source-file digest unchanged | restart-check.json; https-after-restart.json |
| Tunnel restart | New hostname; temporary local DNS failure, then successful HTTPS checks | https-after-tunnel-restart.json |
| Planner | 10 actual MCP calls, zero reported tool errors; localhost | planner-session.jsonl |
| Writer | 19 actual MCP calls, zero reported tool errors; HTTPS; fresh conversation | writer-session.jsonl |
| Handoff result | Guide and exactly three answered quiz questions created, read back and checked | ../workspace/STUDY_GUIDE.md; handoff-after-planner/ |
| Documentation | Native Google Doc, six tables and six rendered pages checked | deliverables.json |

The two successful conversations have distinct IDs recorded in demo-summary.json. The readable transcript preserves actual tool arguments/results; the JSONL files are the original Codex event output. No previous chat was pasted into the Writer prompt. The demo client had shell tools disabled and only the selected MCP tools available. Deletion was not offered to either role.

## Failed attempt and recovery

The first Planner completed its handoff. During the first Writer attempt, the operator ran a crash-recovery test, interrupting calls with HTTP 502 responses. Noninteractive Codex also refused a tool marked as requiring approval under its default policy. The Writer reported a blocker rather than falsely claiming completion.

That genuine trace and intermediate files are retained under first-attempt/. The recovery checks were then completed separately. The runner was configured to approve only the synthetic fixture's write_file and, for Writer, str_replace calls within the already authorized project workspace. The four initial handoff records were restored from the actual setup commit, and the task was run again in two fresh conversations. Those successful transcripts are the main demonstration above; the failed attempt is not hidden or included in the successful call totals.

The tunnel restart initially produced a DNS name that public DNS knew but the default local resolver did not. Clearing the local DNS cache did not immediately resolve it. After the DNS delay, the normal endpoint checker and Writer's actual HTTPS calls succeeded. This is an external availability limitation; a new tunnel must be checked before the live presentation.

## Boundaries and remaining human activities

- Interactive overwrite/delete confirmation is configured in the client example but a human approval dialog was not exercised by the automated demo. A confirm argument is not proof of consent.
- The tests cover a single sequential writer on Windows. They do not prove race resistance against a hostile local user, distributed locking, Windows boot persistence or production readiness.
- The private GitHub repository and owner-private Google Doc must be shared with the intended evaluator before submission. Their visibility was not broadened automatically.
- The technical two-session demonstration was executed. Vince still needs to rehearse/deliver the five-minute live presentation and Q&A himself. No grade is predicted.
- The host must remain awake for local/tunneled use. Temporary public exposure is stopped after verification; npm run tunnel starts another demonstration tunnel when needed.

## Documentation verification

The Google Doc was imported from a title-sanitized DOCX and read back through the connector. All eight tool names, 24-test result, 29-call result and repository link survived. Six native tables were confirmed. Google conversion initially equalized column widths; scoped native formatting restored the intended widths. The final six-page Google PDF was rendered and every page inspected. Local source rendering used installed Microsoft Word and Poppler because LibreOffice was unavailable. QA PDFs and images remain ignored local intermediates, not additional submission outputs.

## Claude Web OAuth update — 2026-10-17

Vince requested Claude Web support. The actual account has no Request headers field; Anthropic documents static headers as a limited organization beta. Added optional single-owner OAuth using the installed MCP SDK's handlers, with exact Claude Web callback registration, S256 PKCE, an independent owner password, CSRF/Origin-protected consent, short-lived single-use codes, expiring access tokens, rotating refresh tokens and revocation. Existing static bearer clients still work. No third-party identity account, database or new dependency was added.

The updated suite passed 31 tests with zero skipped, including an OAuth token reaching the actual MCP handler and both credential types discovering eight tools. The HTTPS check in oauth-checks.json completed discovery, DCR, password-protected consent, code exchange, a real official-client MCP listing, refresh rotation, rejected code/refresh replay and revocation. Negative tests cover wrong passwords, Origin, CSRF, redirects, resources, PKCE, client identity, code expiry, rate limits and oversized bodies. The original clean-clone and Codex session records above remain historical; no Claude conversation is claimed by this automated check.

The existing Google Doc was updated in place and read back. Its security/test wording and new OAuth instructions were checked in exported PDF pages 3, 5 and 7; it now has seven pages. Original tables and earlier demonstration evidence are retained. README includes the exact enable/reconnect procedure. Synthetic Claude test files are separate under workspace/claude-test/.

Runtime at this update: server and HTTPS tunnel running for Vince's immediate test. OAuth registrations and grants are bounded in process memory, so restarting requires re-adding the connector; changing the temporary hostname also requires updating the issuer. Local .env and .local/oauth-login-code.txt hold the private owner password, excluded from Git. Human Claude Web connection and actual Claude tool use remain pending. Stop the tunnel after testing.

Sources: [Claude authentication](https://claude.com/docs/connectors/building/authentication), [testing through a tunnel](https://claude.com/docs/connectors/building/testing).
### Browser approval Origin correction

The first human Claude Web attempt reached the owner form but returned Invalid approval origin. The consent document used Referrer-Policy: no-referrer, which causes browsers to send Origin: null on HTML form POST navigation (MDN Referrer-Policy reference). Changed only the consent GET document to same-origin; OAuth callback redirects retain no-referrer. Origin and CSRF checks remain enforced. Added response-policy regression assertions to the existing consent flow tests. All 31 tests and the real HTTPS OAuth checker passed again after restarting the server. The programmatic checker supplies Origin explicitly, so it did not expose this browser-policy interaction in the original run. A fresh human Claude connection remains required.

Source: https://developer.mozilla.org/en-US/docs/Web/HTTP/Reference/Headers/Referrer-Policy

### Explicit no-sign-in testing mode

Vince reported that the actual browser still rejected Origin after the policy correction and explicitly requested skipping authentication for testing. The browser OAuth failure remains unresolved; programmatic OAuth success is not a successful Claude Web connection.

Added MCP_DEMO_NO_AUTH=1 as an explicit opt-in, default off. In this mode OAuth is disabled and all eight tools are rooted only at workspace/claude-test/. Anyone with the public URL can modify this synthetic folder while exposed. The normal workspace is not exposed by this mode. The updated suite passed 32 tests, including unauthenticated discovery/write and rejection of traversal to a file in the normal workspace. evidence/demo-no-auth-checks.json records real HTTPS calls to all eight tools without credentials, a rejected escape and deletion of the temporary check file.

At handoff the opt-in is enabled locally and the existing tunnel remains running for immediate Claude testing. Select No sign-in and Streamable HTTP. Restore the flag to 0 and restart, or stop the tunnel, after testing. This mode is not the submission's authenticated security demonstration. Human Claude tool use remains pending.
