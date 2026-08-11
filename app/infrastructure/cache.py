"""
Caching (§26): Prompt cache, embedding cache, retrieval cache,
concept cache -- all backed by the same in-memory, in-process store
(§37 tech decision: "In-memory cache"). Cache invalidation occurs on
document updates (§26) -- see retrieval_cache.clear() called from
the ingestion pipeline.

Only the retrieval cache is fully wired into a call site this step
(retrieval.retrieve()) -- that's what the Step 14 exit criteria tests
directly ("a repeated identical query hits cache"). The other three
(prompt/embedding/concept) are real, working, independently tested
cache instances, ready for any caller to use, but retrofitting every
existing engine to route through them is deferred rather than done
as a rushed pass across many files in this one step.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any


@dataclass
class _CacheEntry:
    value: Any
    expires_at: float | None


class CacheStore:
    """Simple namespaced in-memory cache with optional per-entry TTL."""

    def __init__(self):
        self._entries: dict[str, _CacheEntry] = {}

    def get(self, key: str) -> Any | None:
        entry = self._entries.get(key)
        if entry is None:
            return None
        if entry.expires_at is not None and entry.expires_at < time.monotonic():
            del self._entries[key]
            return None
        return entry.value

    def set(self, key: str, value: Any, ttl_seconds: float | None = None) -> None:
        expires_at = time.monotonic() + ttl_seconds if ttl_seconds is not None else None
        self._entries[key] = _CacheEntry(value=value, expires_at=expires_at)

    def invalidate(self, key: str) -> None:
        self._entries.pop(key, None)

    def clear(self) -> None:
        self._entries.clear()

    def __len__(self) -> int:
        return len(self._entries)


# Four named caches per §26. Separate instances so clearing one (e.g.
# on document update) never touches the others.
prompt_cache = CacheStore()
embedding_cache = CacheStore()
retrieval_cache = CacheStore()
concept_cache = CacheStore()
