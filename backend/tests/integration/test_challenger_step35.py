import pytest

from backend.app.application.agents.challenger_agent import ChallengerAgent
from backend.app.domain.models.enums import SourceType
from backend.app.infrastructure.database.models import (
    ArgumentModel,
    DocumentModel,
    PassageModel,
    SourceModel,
)
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
async def test_challenger_agent_safeguards_and_objections(setup_test_env):
    from backend.app.infrastructure.database.session import AsyncSessionLocal
    
    async with AsyncSessionLocal() as session:
        # 1. Setup prerequisite Argument, Source, Document, and Passage
        arg = ArgumentModel(title="Universal Causal Determinism", conclusion_statement="Every event has a deterministic antecedent cause.")
        session.add(arg)
        await session.flush()

        source = SourceModel(title="Buddhist Madhyamaka Text", author="Nagarjuna", source_type=SourceType.PRIMARY)
        session.add(source)
        await session.flush()

        doc = DocumentModel(source_id=source.id, checksum_sha256="chal_hash_999", mime_type="text/plain")
        session.add(doc)
        await session.flush()

        passage = PassageModel(document_id=doc.id, page_number=20, content="Things do not arise from themselves, nor from others, nor from both, nor without cause.")
        session.add(passage)
        await session.commit()

        # 2. Run the current claim-level Challenger contract
        challenger = ChallengerAgent(session)
        result = await challenger.challenge_claim(
            "Every event has a deterministic antecedent cause."
        )

        # 3. Assertions & Checkpoints Verification
        assert result["claim"] == arg.conclusion_statement
        assert result["objections"]
        assert result["counterarguments"]

        # Safeguard: Challenger rejects ungrounded/manufactured objections
        empty_result = await challenger.challenge_claim("")
        assert empty_result["objections"]
