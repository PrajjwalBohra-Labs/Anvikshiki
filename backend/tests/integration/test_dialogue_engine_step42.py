import pytest

from backend.app.application.use_cases.dialogue_engine import DialogueEngine
from backend.app.domain.models.enums import SourceType
from backend.app.infrastructure.database.models import (
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
async def test_dialogue_engine_modes_and_disagreement(setup_test_env):
    from backend.app.infrastructure.database.session import AsyncSessionLocal
    
    async with AsyncSessionLocal() as session:
        # 1. Setup prerequisite Source, Document, and Passage
        source = SourceModel(title="Pramana Vartika", author="Dignaga", source_type=SourceType.PRIMARY)
        session.add(source)
        await session.flush()

        doc = DocumentModel(source_id=source.id, checksum_sha256="diag_hash_555", mime_type="text/plain")
        session.add(doc)
        await session.flush()

        passage = PassageModel(document_id=doc.id, page_number=14, content="Cognition is characterized by luminous self-awareness.")
        session.add(passage)
        await session.commit()

        engine_service = DialogueEngine(session)

        # 2. Test Challenge / Disagreement Mode backed by evidence
        res_challenge = await engine_service.generate_response(
            user_utterance="Consciousness requires no self-awareness.",
            dialogue_mode="challenge",
            evidence_passage_id=passage.id
        )
        assert res_challenge["disagrees_with_user"] is True
        assert res_challenge["evidence_linked"] is True
        assert res_challenge["source_title"] == "Pramana Vartika"
        assert "Pramana Vartika" in res_challenge["response_text"]

        # 3. Test Mastery Bypass (Avoid unnecessary explanation)
        res_mastery = await engine_service.generate_response(
            user_utterance="I understand perception thoroughly.",
            dialogue_mode="explanation",
            user_mastery_demonstrated=True
        )
        assert res_mastery["dialogue_mode"] == "reflective"  # Shifted away from redundant explanation

        # 4. Test Socratic Questioning
        res_socratic = await engine_service.generate_response(
            user_utterance="All knowledge comes from testimony.",
            dialogue_mode="socratic"
        )
        assert res_socratic["preserves_uncertainty"] is True
        assert "?" in res_socratic["response_text"]