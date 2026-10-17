# Implementation and verification record

Date: 2026-10-17, Asia/Manila. Scope: CSE2 Midterms Part 1.

## Observed results

| Check | Result | Evidence |
| --- | --- | --- |
| Focused Python tests | 24 passed, zero skipped | tests/; clean-checkout.json |
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
