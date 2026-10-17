# Study guide: MCP, safe tools and handoff

Based only on the synthetic demonstration notes `notes/mcp-basics.md` and `notes/safe-tools.md`.

## MCP basics

MCP is a standard way for an AI application to access tools and context. MCP itself is not an AI model and does not make plans.

- **Host:** The AI application that manages the model and conversation.
- **Client:** A component inside the host that connects to an MCP server.
- **Server:** Exposes tools for bounded operations, such as reading a file.

The model's tool-use loop is: **choose a tool → supply arguments → observe the result → decide the next step**.

## Safe tool use

- A **sandbox** restricts tools to one workspace folder.
- **Path traversal** tries to escape that folder, for example with `../outside.txt`.
- **Authentication** checks that a caller has the expected credential.
- Read a file before editing it, and request confirmation before destructive changes.
- Use small reads and literal searches instead of repeatedly dumping whole files.

## Saved handoff

Save the **goal**, **completed work** and **exact next step** so another session can continue. The four handoff records are:

- `PROJECT_STATE.md`
- `PLAN_LOG.md`
- `CHECKPOINTS.md`
- `DECISIONS.md`

## Three-question quiz with answers

1. **What do the host, client and server do, and what is the model's tool-use loop?**
   **Answer:** The host manages the model and conversation; a client inside the host connects to an MCP server; the server exposes tools for bounded operations. The model chooses a tool, supplies arguments, observes the result and decides the next step. MCP itself is not a model and does not make plans.

2. **How do sandboxing and authentication support safe tool use, and what practices should accompany them?**
   **Answer:** A sandbox restricts tools to one workspace folder; path traversal tries to escape it, such as with `../outside.txt`. Authentication checks for the expected credential. Read before editing, request confirmation before destructive changes, and use small reads and literal searches instead of repeatedly dumping whole files.

3. **What should be saved for another session, and which files hold the handoff records?**
   **Answer:** Save the goal, completed work and exact next step. The records are `PROJECT_STATE.md`, `PLAN_LOG.md`, `CHECKPOINTS.md` and `DECISIONS.md`.
