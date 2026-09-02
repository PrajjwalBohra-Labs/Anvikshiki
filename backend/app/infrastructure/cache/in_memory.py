"""Failure-tolerant TTL cache for non-sensitive, globally readable metadata."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from time import monotonic
from typing import Any

import structlog

logger = structlog.get_logger(__name__)


@dataclass
class _Entry:
    value: Any
    expires_at: float


class InMemoryTTLCache:
    """A bounded-scope cache with deterministic keys and fail-open callers."""

    def __init__(self, ttl_seconds: float = 30.0):
        if ttl_seconds <= 0:
            raise ValueError("Cache TTL must be positive.")
        self.ttl_seconds = ttl_seconds
        self._entries: dict[str, _Entry] = {}

    def get(self, key: str) -> Any | None:
        entry = self._entries.get(key)
        if entry is None:
            logger.info("cache_miss", cache_name="source_metadata")
            return None
        if entry.expires_at <= monotonic():
            self._entries.pop(key, None)
            logger.info("cache_expired", cache_name="source_metadata")
            return None
        logger.info("cache_hit", cache_name="source_metadata")
        return deepcopy(entry.value)

    def set(self, key: str, value: Any) -> None:
        self._entries[key] = _Entry(deepcopy(value), monotonic() + self.ttl_seconds)
        logger.info("cache_populated", cache_name="source_metadata")

    def invalidate(self, key: str) -> None:
        self._entries.pop(key, None)
        logger.info("cache_invalidated", cache_name="source_metadata")

    def clear(self) -> None:
        self._entries.clear()
