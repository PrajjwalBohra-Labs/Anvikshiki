"""
Memory engine (§10 Memory Model + Memory Pipeline).

Seven tiers, split by lifetime:
  - In-process only (cleared on restart): Working Memory, Dialogue
    Memory, Session Memory.
  - Persistent (survives restarts), backed by the relational store's
    dedicated memory_records table: Concept Memory, Project Memory,
    Research Memory, System Memory.

Memory Pipeline: Interaction -> Extraction -> Classification ->
Persistence. Classification reads an explicit tier hint, defaulting
to Working Memory -- a placeholder for smarter classification later
(§17 replaceability).

Publishes MemoryUpdated (§25 Events) after every successful write --
this is the single choke point for all memory writes regardless of
caller, so it's the natural place for that notification to live.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from functools import lru_cache

from app.infrastructure.event_bus import EventBus, EventName, get_event_bus
from app.persistence import relational_db


class MemoryTier(str, Enum):
    WORKING = "working"
    DIALOGUE = "dialogue"
    SESSION = "session"
    CONCEPT = "concept"
    PROJECT = "project"
    RESEARCH = "research"
    SYSTEM = "system"


IN_MEMORY_TIERS = {MemoryTier.WORKING, MemoryTier.DIALOGUE, MemoryTier.SESSION}
PERSISTENT_TIERS = {MemoryTier.CONCEPT, MemoryTier.PROJECT, MemoryTier.RESEARCH, MemoryTier.SYSTEM}


@dataclass
class MemoryRecord:
    id: str
    tier: MemoryTier
    content: str
    scope_id: str | None
    metadata: dict = field(default_factory=dict)
    created_at: str = ""


class InMemoryTierStore:
    def __init__(self, tier: MemoryTier):
        self._tier = tier
        self._records: dict[str, MemoryRecord] = {}

    def write(self, content: str, scope_id: str | None = None, metadata: dict | None = None) -> MemoryRecord:
        record = MemoryRecord(
            id=str(uuid.uuid4()), tier=self._tier, content=content, scope_id=scope_id,
            metadata=metadata or {}, created_at=datetime.now(timezone.utc).isoformat(),
        )
        self._records[record.id] = record
        return record

    def read(self, memory_id: str) -> MemoryRecord | None:
        return self._records.get(memory_id)


class PersistentTierStore:
    def __init__(self, tier: MemoryTier):
        self._tier = tier

    def write(self, content: str, scope_id: str | None = None, metadata: dict | None = None) -> MemoryRecord:
        memory_id = relational_db.create_memory_record(
            tier=self._tier.value, scope_id=scope_id, content=content, metadata=metadata or {}
        )
        return _row_to_record(relational_db.get_memory_record(memory_id))

    def read(self, memory_id: str) -> MemoryRecord | None:
        row = relational_db.get_memory_record(memory_id)
        if row is None or row["tier"] != self._tier.value:
            return None
        return _row_to_record(row)


def _row_to_record(row: dict) -> MemoryRecord:
    metadata = row["metadata"]
    if isinstance(metadata, str):
        metadata = json.loads(metadata)
    return MemoryRecord(
        id=row["id"], tier=MemoryTier(row["tier"]), content=row["content"],
        scope_id=row["scope_id"], metadata=metadata or {}, created_at=row["created_at"],
    )


class MemoryEngine:
    """Orchestrates the Memory Pipeline across all seven tiers."""

    def __init__(self, event_bus: EventBus | None = None):
        self._stores: dict[MemoryTier, InMemoryTierStore | PersistentTierStore] = {
            tier: InMemoryTierStore(tier) for tier in IN_MEMORY_TIERS
        }
        self._stores.update({tier: PersistentTierStore(tier) for tier in PERSISTENT_TIERS})
        self._event_bus = event_bus or get_event_bus()

    def _extract(self, interaction: dict) -> str:
        content = interaction.get("content")
        if not content:
            raise ValueError("Interaction must include non-empty 'content'")
        return str(content).strip()

    def _classify(self, interaction: dict) -> MemoryTier:
        tier_hint = interaction.get("tier")
        return MemoryTier.WORKING if tier_hint is None else MemoryTier(tier_hint)

    def _persist(self, tier: MemoryTier, content: str, scope_id: str | None, metadata: dict) -> MemoryRecord:
        return self._stores[tier].write(content, scope_id=scope_id, metadata=metadata)

    def remember(self, interaction: dict) -> MemoryRecord:
        """Runs Interaction -> Extraction -> Classification -> Persistence."""
        content = self._extract(interaction)
        tier = self._classify(interaction)
        scope_id = interaction.get("scope_id")
        metadata = interaction.get("metadata", {})
        record = self._persist(tier, content, scope_id, metadata)

        self._event_bus.publish(
            EventName.MEMORY_UPDATED, {"memory_id": record.id, "tier": tier.value, "scope_id": scope_id}
        )
        return record

    def recall(self, tier: MemoryTier, memory_id: str) -> MemoryRecord | None:
        return self._stores[tier].read(memory_id)


@lru_cache
def get_memory_engine() -> MemoryEngine:
    return MemoryEngine()
