import pytest

from backend.app.application.agents.source_critic_agent import SourceCriticAgent
from backend.app.domain.models.enums import EvidenceStatus, SourceType
from backend.app.infrastructure.database.models import SourceModel
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
async def test_source_critic_agent_evaluation_and_safeguards(setup_test_env):
    from backend.app.infrastructure.database.session import AsyncSessionLocal
    
    async with AsyncSessionLocal() as session:
        # 1. Setup prerequisite Source
        source = SourceModel(title="Commentary on Brahmasutra", author="Shankara", source_type=SourceType.PRIMARY)
        session.add(source)
        await session.commit()

        # 2. Run Source Critic Agent
        critic_agent = SourceCriticAgent(session)
        result = await critic_agent.evaluate_source(
            source_id=source.id,
            finding="Translation exhibits secondary interpretive filtering on technical terms.",
            basis="Comparison against Sanskrit root vocabulary indicates rendering divergence in verse 2.1.",
            confidence=0.88,
            status=EvidenceStatus.CONTESTED,
            supporting_payload={"root_term": "Adhyasa", "translation_used": "Superimposition"}
        )

        # 3. Assertions & Checkpoints Verification
        assert result["criticism_id"] is not None
        assert result["inspectable"] is True
        assert result["status"] == EvidenceStatus.CONTESTED

        # Safeguard: Critic rejects findings lacking a factual basis (no unsupported accusations)
        with pytest.raises(ValueError, match="Source criticism rejected"):
            await critic_agent.evaluate_source(
                source_id=source.id,
                finding="Baseless accusation",
                basis=""
            )