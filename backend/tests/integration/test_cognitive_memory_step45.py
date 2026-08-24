import pytest
from backend.app.infrastructure.database.session import engine, Base
from backend.app.infrastructure.database.models import UserModel
from backend.app.application.memory.cognitive_memory import CognitiveMemoryService

@pytest.fixture
async def setup_test_env():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

@pytest.mark.asyncio
async def test_cognitive_memory_observables_and_inspection(setup_test_env):
    from backend.app.infrastructure.database.session import AsyncSessionLocal
    
    async with AsyncSessionLocal() as session:
        user = UserModel(username="cognitive_scholar")
        session.add(user)
        await session.commit()

        service = CognitiveMemoryService(session)

        # 1. Record valid observable reasoning pattern
        obs = await service.record_observation(
            user_id=user.id,
            observation_type="ability to distinguish evidence/interpretation",
            observation_detail="Correctly separated primary textual passage from scholarly commentary.",
            evidence_reference="Passage reference pass_456 in dialogue turn 2",
            originating_interaction_id="msg_789",
            confidence=0.95
        )
        assert obs.id is not None
        assert obs.is_evidence_linked is True

        # 2. Inspect observations
        observations = await service.inspect_observations(user.id)
        assert len(observations) == 1
        assert observations[0]["observation_type"] == "ability to distinguish evidence/interpretation"

        # 3. Test safeguards against invalid observation types or unlinked evidence
        with pytest.raises(ValueError, match="Invalid observation type"):
            await service.record_observation(
                user_id=user.id,
                observation_type="unsupported personality label",
                observation_detail="Stub",
                evidence_reference="Ref",
                originating_interaction_id="msg_1"
            )

        with pytest.raises(ValueError, match="Cognitive observation rejected"):
            await service.record_observation(
                user_id=user.id,
                observation_type="source-checking behavior",
                observation_detail="Stub",
                evidence_reference="",
                originating_interaction_id="msg_1"
            )

        # 4. Test user deletion control
        deleted = await service.delete_observation(obs.id, user.id)
        assert deleted is True
        assert len(await service.inspect_observations(user.id)) == 0