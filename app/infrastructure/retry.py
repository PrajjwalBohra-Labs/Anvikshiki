"""
Retry helper (§29 recoverable path: retry). Simple exponential
backoff, stdlib only -- not worth a dependency for something this
small.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import TypeVar

T = TypeVar("T")

DEFAULT_MAX_ATTEMPTS = 3
DEFAULT_BASE_DELAY_SECONDS = 0.5


def retry_with_backoff(
    func: Callable[[], T],
    exceptions: tuple[type[Exception], ...],
    max_attempts: int = DEFAULT_MAX_ATTEMPTS,
    base_delay: float = DEFAULT_BASE_DELAY_SECONDS,
) -> T:
    last_exception: Exception | None = None
    for attempt in range(max_attempts):
        try:
            return func()
        except exceptions as exc:
            last_exception = exc
            if attempt < max_attempts - 1:
                time.sleep(base_delay * (2**attempt))
    raise last_exception
