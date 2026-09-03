from uuid import uuid4

import pytest
from sqlalchemy import delete

from backend.app.application.memory.memory_foundation import MemoryFoundationService
from backend.app.infrastructure.database.models import MemoryRecordModel, UserModel
from backend.app.infrastructure.database.session import AsyncSessionLocal, engine


@pytest.fixture
async def memory_database():
    async with engine.begin() as connection:
        await connection.run_sync(UserModel.__table__.create, checkfirst=True)
        await connection.run_sync(MemoryRecordModel.__table__.create, checkfirst=True)
    yield


@pytest.mark.asyncio
async def test_memory_foundation_is_durable_owned_and_tiered(memory_database):
    username = f"memory-owner-{uuid4().hex}"
    other_username = f"memory-other-{uuid4().hex}"

    async with AsyncSessionLocal() as session:
        owner = UserModel(username=username)
        other = UserModel(username=other_username)
        session.add_all([owner, other])
        await session.flush()

        service = MemoryFoundationService(session)
        epistemic = await service.record_memory(
            user_id=owner.id,
            memory_tier="epistemic",
            content="User accepts Nyaya realism regarding perceptual objects.",
            confidence=0.92,
            provenance_source_id="source_nyaya_01",
            source_event="Dialogue turn 4",
        )
        working = await service.record_memory(
            user_id=owner.id,
            memory_tier="working",
            content="Active search query parameters for Buddhist epistemology.",
            confidence=1.0,
            retention_policy="transient",
        )
        await service.record_memory(
            user_id=other.id,
            memory_tier="epistemic",
            content="Private memory belonging to another user.",
        )
        owner_id = owner.id
        other_id = other.id
        epistemic_id = epistemic["memory_id"]
        working_id = working["memory_id"]

    # A fresh service/session proves records are database-backed rather than
    # stored in the lifetime of one service instance.
    async with AsyncSessionLocal() as session:
        service = MemoryFoundationService(session)
        epistemic_memories = await service.inspect_memories(
            user_id=owner_id,
            memory_tier="epistemic",
            min_confidence=0.9,
        )
        assert [memory["memory_id"] for memory in epistemic_memories] == [epistemic_id]
        assert epistemic_memories[0]["provenance_source_id"] == "source_nyaya_01"
        assert epistemic_memories[0]["is_evidence_linked"] is True

        other_memories = await service.inspect_memories(user_id=other_id)
        assert len(other_memories) == 1
        assert other_memories[0]["content"] == "Private memory belonging to another user."

        cleared_count = await service.clear_tier(owner_id, "working")
        assert cleared_count == 1
        assert await service.inspect_memories(user_id=owner_id, memory_tier="working") == []

        assert await session.get(MemoryRecordModel, working_id) is None
        await session.execute(
            delete(MemoryRecordModel).where(
                MemoryRecordModel.user_id.in_([owner_id, other_id])
            )
        )
        await session.execute(delete(UserModel).where(UserModel.id.in_([owner_id, other_id])))
        await session.commit()


@pytest.mark.asyncio
async def test_memory_foundation_validates_tier_content_and_confidence(memory_database):
    username = f"memory-validation-{uuid4().hex}"
    async with AsyncSessionLocal() as session:
        user = UserModel(username=username)
        session.add(user)
        await session.flush()
        service = MemoryFoundationService(session)

        with pytest.raises(ValueError, match="Invalid memory tier"):
            await service.record_memory(user.id, "invalid_tier", "Bad memory")
        with pytest.raises(ValueError, match="content cannot be empty"):
            await service.record_memory(user.id, "working", "   ")
        with pytest.raises(ValueError, match="between 0 and 1"):
            await service.record_memory(user.id, "working", "Bad confidence", confidence=1.1)

        await session.execute(delete(UserModel).where(UserModel.id == user.id))
        await session.commit()
