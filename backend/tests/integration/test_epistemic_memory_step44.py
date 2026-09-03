import pytest

from backend.app.application.memory.epistemic_memory import EpistemicMemoryService
from backend.app.infrastructure.database.models import UserModel
from backend.app.infrastructure.database.session import Base, engine


@pytest.fixture
async def setup_test_env():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

@pytest.mark.asyncio
async def test_epistemic_memory_persistence_and_history(setup_test_env):
    from backend.app.infrastructure.database.session import AsyncSessionLocal
    
    async with AsyncSessionLocal() as session:
        user = UserModel(username="epistemic_scholar")
        session.add(user)
        await session.commit()

        service = EpistemicMemoryService(session)

        # 1. Record position
        pos = await service.record_position(
            user_id=user.id,
            claim_statement="Perception is an infallible source of valid knowledge.",
            position="tentative",
            confidence=0.8,
            supporting_evidence=[{"passage_id": "p_1", "text": "Direct sense contact..."}],
            counterarguments=[{"text": "Illusory perception occurs."}],
            status="tentative"
        )
        assert pos.id is not None
        assert pos.status == "tentative"

        # 2. Update position status (Position changes and retains history)
        updated = await service.update_position_status(
            position_id=pos.id,
            new_status="contested",
            change_reason="Encountered counterargument regarding illusory perception."
        )
        assert updated.status == "contested"

        # 3. Retrieve and inspect positions & history
        positions = await service.get_user_positions(user.id)
        assert len(positions) == 1
        assert positions[0]["status"] == "contested"
        assert len(positions[0]["history"]) == 1
        assert positions[0]["history"][0]["previous_status"] == "tentative"
        assert positions[0]["history"][0]["new_status"] == "contested"
        assert positions[0]["history"][0]["change_reason"] == "Encountered counterargument regarding illusory perception."