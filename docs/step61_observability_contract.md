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
