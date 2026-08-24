import pytest
from backend.app.infrastructure.database.session import engine, Base
from backend.app.infrastructure.database.models import ArgumentModel, SourceModel, DocumentModel, PassageModel
from backend.app.domain.models.enums import SourceType
from backend.app.application.agents.challenger_agent import ChallengerAgent

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

        # 2. Run Challenger Agent
        challenger = ChallengerAgent(session)
        result = await challenger.challenge_argument(
            argument_id=arg.id,
            counter_evidence_passage_id=passage.id,
            objection_statement="Causal origination fails under rigorous interdependence analysis.",
            is_genuine_contradiction=True
        )

        # 3. Assertions & Checkpoints Verification
        assert result["objection_id"] is not None
        assert result["is_evidence_linked"] is True
        assert result["is_genuine_contradiction"] is True
        assert result["counter_evidence_passage_id"] == passage.id

        # Safeguard: Challenger rejects ungrounded/manufactured objections
        with pytest.raises(ValueError, match="Challenger rejection"):
            await challenger.challenge_argument(
                argument_id=arg.id,
                objection_statement=""
            )