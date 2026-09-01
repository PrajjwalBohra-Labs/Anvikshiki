# Step 61 — Observability Contract

## Contract discovery

The repository already contains structlog configuration, subsystem logs, MCP
audit events, and health reporting, but request-level correlation was not
wired into the application. No separate historical Step 61 specification was
found.

## Contract

Each HTTP request receives a server-generated opaque request ID, emits a
structured completion/failure event with method, route template, status, and
duration, and returns the ID in `X-Request-ID`. Health reporting remains the
existing application/database/pgvector/model/MCP status contract.

Sensitive arguments and exception text are excluded from request/error logs.
