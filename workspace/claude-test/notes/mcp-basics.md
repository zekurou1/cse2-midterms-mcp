# Sample note: MCP basics

Synthetic demonstration notes for a small study-guide task.

MCP is a standard way for an AI application to access tools and context.
The host is the AI application that manages the model and conversation.
A client inside the host connects to an MCP server.
The server exposes tools that perform bounded operations, such as reading a file.
The model chooses a tool, supplies arguments, observes the result, and decides the next step.
MCP itself is not an AI model and does not make plans.
