# Step 39: MCP Foundation

Anvikshiki uses the official `mcp==2.0.0` SDK as its protocol boundary. The
compatibility wrapper is `AnvikshikiMCPServer` in
`backend.app.infrastructure.mcp.server`; it preserves the existing
in-process registration API while delegating MCP protocol initialization and
transport handling to the SDK.

Tools are registered with explicit JSON Schemas. Schemas are made closed by
default (`additionalProperties: false`) and validated before permission checks
or handler execution. Permission policies receive the tool name and validated
arguments. Audit logs contain the tool name, argument keys, and authentication
presence, never argument values or credentials. Handler failures return stable,
non-sensitive errors while detailed exceptions remain server-side logs.

The foundation exposes the official SDK stdio transport through:

```powershell
.\.venv\Scripts\python.exe -m backend.app.infrastructure.mcp
```

This foundation task does not register research-specific tools. Those belong to
STEP 40.
