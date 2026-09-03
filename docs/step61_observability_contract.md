# Step 61 — Observability Contract

No historical Step 61 specification was found in the repository or Git history.

The minimum contract established from the existing FastAPI, structlog, MCP, and
health-check architecture is:

- every HTTP request receives a non-sensitive correlation ID;
- structured request events record method, route template, status, and duration;
- failures record safe exception types without credentials, payloads, URLs, or
  stack traces in user-facing responses;
- health failures remain operationally visible while returning sanitized status;
- API responses remain private and security headers are applied consistently;
- existing service and MCP logs remain responsible for domain-operation context.

No external metrics, tracing platform, Redis, or new logging dependency is
required by the discoverable architecture.
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
