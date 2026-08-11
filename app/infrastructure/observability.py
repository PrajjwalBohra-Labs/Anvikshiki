"""
Observability (§28): trace ID per request, execution traces, latency
metrics, token usage, retrieval statistics, engine failure tracking.

Trace IDs propagate via a contextvars.ContextVar rather than being
threaded through every function signature -- the same pattern real
frameworks use for request-scoped state. This means existing engines
(including the Reasoning Engine, which deliberately has no
llm_adapter parameter -- Step 8) don't need new parameters to become
traceable; they just call record_event() using the ambient trace ID.
record_event() is a safe no-op when no trace is active (e.g. a
standalone call in a test with no request context).
"""

from __future__ import annotations

import time
import uuid
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from datetime import datetime, timezone

_current_trace_id: ContextVar[str | None] = ContextVar("current_trace_id", default=None)


@dataclass
class TraceEvent:
    trace_id: str
    stage: str
    event_type: str  # "stage_start", "stage_end", "failure", "metric"
    timestamp: str
    duration_ms: float | None = None
    metadata: dict = field(default_factory=dict)


class TraceStore:
    """In-memory, per-trace event log (§26/§37 in-memory infra philosophy)."""

    def __init__(self):
        self._traces: dict[str, list[TraceEvent]] = {}

    def record(self, event: TraceEvent) -> None:
        self._traces.setdefault(event.trace_id, []).append(event)

    def get_trace(self, trace_id: str) -> list[TraceEvent]:
        return list(self._traces.get(trace_id, []))

    def clear(self) -> None:
        self._traces.clear()


_trace_store = TraceStore()


def get_trace_store() -> TraceStore:
    return _trace_store


def new_trace_id() -> str:
    return str(uuid.uuid4())


def set_current_trace_id(trace_id: str) -> None:
    _current_trace_id.set(trace_id)


def get_current_trace_id() -> str | None:
    return _current_trace_id.get()


def record_event(stage: str, event_type: str, duration_ms: float | None = None, **metadata) -> None:
    trace_id = get_current_trace_id()
    if trace_id is None:
        return
    _trace_store.record(
        TraceEvent(
            trace_id=trace_id,
            stage=stage,
            event_type=event_type,
            timestamp=datetime.now(timezone.utc).isoformat(),
            duration_ms=duration_ms,
            metadata=metadata,
        )
    )


@contextmanager
def trace_stage(stage: str, **metadata):
    """Records stage_start/stage_end with latency, and a failure
    event (with the exception re-raised) if the stage raises."""
    start = time.monotonic()
    record_event(stage, "stage_start", **metadata)
    try:
        yield
    except Exception as exc:
        duration_ms = (time.monotonic() - start) * 1000
        record_event(stage, "failure", duration_ms=duration_ms, error=str(exc), error_type=type(exc).__name__)
        raise
    else:
        duration_ms = (time.monotonic() - start) * 1000
        record_event(stage, "stage_end", duration_ms=duration_ms)
