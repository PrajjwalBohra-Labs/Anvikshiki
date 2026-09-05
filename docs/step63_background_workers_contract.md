# Step 63 - Background Workers Contract

No historical Step 63 specification or implementation was found in the
repository or Git history. This document establishes the smallest contract
supported by the existing durable research-run and LangGraph checkpoint
architecture.

## Scope

Step 63 provides durable background execution for the existing research
workflow. It does not replace the existing synchronous or SSE research
endpoints and does not add an external queue.

## Job contract

- `POST /api/v1/research/jobs` creates an authenticated, user-owned research
  job with a required idempotency key.
- The request contains only research parameters (`query`, optional `domain`
  and `depth`) and no owner identifier, command, path, or arbitrary URL.
- The job ID is deterministic for the authenticated user, job type, and
  idempotency key. Repeating the request returns the existing job.
- `GET /api/v1/research/jobs/{job_id}` returns only the authenticated user's
  job. `POST .../{job_id}/cancel` requests cancellation before execution.
- States are `PENDING`, `RUNNING`, `COMPLETED`, `FAILED`, and `CANCELLED`.
- The default retry policy permits three bounded attempts. A retryable failure
  returns to `PENDING`; exhaustion produces `FAILED` with a sanitized error.

## Worker contract

The worker polls the durable job table in-process. It claims one pending job,
executes the existing `ResearchWorkflowEngine`, records the result, and
releases or fails the job. Pending jobs survive process restarts. Stale
`RUNNING` jobs are requeued on worker startup. Claiming is transactionally
guarded for database backends that support row locks.

## Security and observability

Authentication and ownership are checked before creation, status, or cancel
operations. The database row is the source of truth; Step 62 cache state is
not used. Logs contain job identity, type, state, attempt, duration, and safe
error type only. Job payloads, credentials, tokens, and raw exceptions are
never logged or returned.
