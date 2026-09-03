"""Durable generic memory foundation for the Step 43 contract."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from typing import Any

import structlog
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.infrastructure.database.models import MemoryRecordModel

logger = structlog.get_logger(__name__)


class MemoryFoundationService:
    """Persist and inspect user-owned memory across the defined tiers.

    This generic foundation stores references to provenance; it does not turn
    arbitrary text into evidence or create a second provenance graph. The
    specialized epistemic and cognitive services remain separate contracts.
    """

    VALID_TIERS = frozenset(
        {
            "working",
            "dialogue",
            "session",
            "research",
            "cognitive",
            "epistemic",
            "misconception",
        }
    )

    def __init__(self, session: AsyncSession):
        self.session = session

    @classmethod
    def _validate_tier(cls, memory_tier: str) -> None:
        if not isinstance(memory_tier, str) or memory_tier not in cls.VALID_TIERS:
            raise ValueError(
                f"Invalid memory tier '{memory_tier}'. Must be one of {sorted(cls.VALID_TIERS)}."
            )

    @staticmethod
    def _validate_owner(user_id: str) -> None:
        if not isinstance(user_id, str) or not user_id.strip():
            raise ValueError("Memory records require an owning user.")

    @staticmethod
    def _validate_content(content: str) -> None:
        if not isinstance(content, str) or not content.strip():
            raise ValueError("Memory content cannot be empty.")

    @staticmethod
    def _validate_confidence(confidence: float) -> None:
        if not isinstance(confidence, (int, float)) or isinstance(confidence, bool):
            raise TypeError("Memory confidence must be a number between 0 and 1.")
        if not 0.0 <= float(confidence) <= 1.0:
            raise ValueError("Memory confidence must be a number between 0 and 1.")

    @staticmethod
    def _as_public(memory: MemoryRecordModel) -> dict[str, Any]:
        timestamp: datetime = memory.created_at
        return {
            "memory_id": memory.id,
            "user_id": memory.user_id,
            "memory_tier": memory.memory_tier,
            "content": memory.content,
            "confidence": memory.confidence,
            "provenance_source_id": memory.provenance_source_id,
            "source_event": memory.source_event,
            "retention_policy": memory.retention_policy,
            "timestamp": timestamp.isoformat(),
            "is_evidence_linked": bool(memory.provenance_source_id),
        }

    async def record_memory(
        self,
        user_id: str,
        memory_tier: str,
        content: str,
        confidence: float = 1.0,
        provenance_source_id: str | None = None,
        source_event: str | None = None,
        retention_policy: str = "durable",
    ) -> dict[str, Any]:
        """Create one owned memory record and return its stable public shape."""

        self._validate_owner(user_id)
        self._validate_tier(memory_tier)
        self._validate_content(content)
        self._validate_confidence(confidence)
        if not isinstance(retention_policy, str) or not retention_policy.strip():
            raise ValueError("Memory retention policy cannot be empty.")
        if source_event is not None and (
            not isinstance(source_event, str) or not source_event.strip()
        ):
            raise ValueError("Memory source event cannot be empty.")

        memory = MemoryRecordModel(
            user_id=user_id,
            memory_tier=memory_tier,
            content=content,
            confidence=float(confidence),
            provenance_source_id=provenance_source_id,
            source_event=source_event or "interaction",
            retention_policy=retention_policy,
        )
        self.session.add(memory)
        await self.session.commit()
        await self.session.refresh(memory)
        logger.info("memory_recorded", memory_id=memory.id, memory_tier=memory_tier)
        return self._as_public(memory)

    async def inspect_memories(
        self,
        user_id: str,
        memory_tier: str | None = None,
        min_confidence: float = 0.0,
    ) -> list[dict[str, Any]]:
        """Return only the owner's records in deterministic creation order."""

        self._validate_owner(user_id)
        if memory_tier is not None:
            self._validate_tier(memory_tier)
        self._validate_confidence(min_confidence)

        stmt = (
            select(MemoryRecordModel)
            .where(
                MemoryRecordModel.user_id == user_id,
                MemoryRecordModel.confidence >= float(min_confidence),
            )
            .order_by(MemoryRecordModel.created_at.asc(), MemoryRecordModel.id.asc())
        )
        if memory_tier is not None:
            stmt = stmt.where(MemoryRecordModel.memory_tier == memory_tier)
        result = await self.session.execute(stmt)
        return [self._as_public(memory) for memory in result.scalars().all()]

    async def clear_tier(self, user_id: str, memory_tier: str) -> int:
        """Delete all records in one tier for one owner and return the count."""

        self._validate_owner(user_id)
        self._validate_tier(memory_tier)
        records = await self.session.execute(
            select(MemoryRecordModel.id).where(
                MemoryRecordModel.user_id == user_id,
                MemoryRecordModel.memory_tier == memory_tier,
            )
        )
        memory_ids: Sequence[str] = records.scalars().all()
        if not memory_ids:
            return 0
        await self.session.execute(
            delete(MemoryRecordModel).where(MemoryRecordModel.id.in_(memory_ids))
        )
        await self.session.commit()
        logger.info("memory_tier_cleared", memory_tier=memory_tier, count=len(memory_ids))
        return len(memory_ids)
