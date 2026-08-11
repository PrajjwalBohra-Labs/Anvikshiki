"""
Rate limiting (§27). In-memory sliding-window limiter, per API key --
matches the project'"'"'s in-memory, no-external-dependency philosophy
(§26/§37) rather than pulling in Redis for a local single-user app.
"""

from __future__ import annotations

import time
from collections import defaultdict, deque

from fastapi import Header, HTTPException, status

from app.config import get_settings
from app.security.audit_log import log_security_event

_WINDOW_SECONDS = 60.0
_request_log: dict[str, deque] = defaultdict(deque)


def _check_rate_limit(identity: str, limit: int) -> None:
    now = time.monotonic()
    window = _request_log[identity]

    while window and window[0] < now - _WINDOW_SECONDS:
        window.popleft()

    if len(window) >= limit:
        log_security_event("rate_limit_exceeded", {"identity": identity})
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Rate limit exceeded")

    window.append(now)


def rate_limit_dependency(x_api_key: str | None = Header(default=None)) -> None:
    settings = get_settings()
    identity = x_api_key or "anonymous"
    _check_rate_limit(identity, settings.rate_limit_requests_per_minute)


def reset_rate_limits() -> None:
    """Test helper -- clears all rate-limit state between tests."""
    _request_log.clear()
