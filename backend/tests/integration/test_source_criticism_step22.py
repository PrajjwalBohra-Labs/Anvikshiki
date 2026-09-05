import pytest

from backend.app.application.use_cases.source_criticism_service import (
    SourceCriticismEngine,
)
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
async def test_source_criticism_evaluation(setup_test_env):
    from backend.app.infrastructure.database.session import AsyncSessionLocal
    
    async with AsyncSessionLocal() as session:
        # 1. Setup neutral scholarly source
        source = SourceModel(
            title="Arthashastra",
            author="Kautilya",
            historical_era="Maurya Empire",
            original_language="Sanskrit",
            source_type=SourceType.PRIMARY
        )
        session.add(source)
        await session.commit()

        # 2. Run Source Criticism Engine
        engine_service = SourceCriticismEngine(session)
        criticism = await engine_service.evaluate_source(
            source_id=source.id,
            finding="The text reflects administrative pragmatism rather than purely religious dogmatic rule.",
            basis="Analysis of internal taxation and interstate diplomacy chapters.",
            confidence=0.92,
            status=EvidenceStatus.SUPPORTED,
            supporting_evidence={"passage_ref": "Book 2, Chapter 6"},
            contradicting_evidence={"alternative_interpretation": "Some secondary commentaries emphasize moral duty over statecraft."}
        )

        # 3. Assertions & Checkpoints Verification
        assert criticism.id is not None
        assert criticism.status == EvidenceStatus.SUPPORTED
        assert criticism.confidence == 0.92
        assert "administrative pragmatism" in criticism.finding
        assert criticism.supporting_evidence_payload["passage_ref"] == "Book 2, Chapter 6"