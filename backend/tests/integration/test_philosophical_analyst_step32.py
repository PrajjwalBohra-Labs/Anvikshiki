import pytest
from backend.app.infrastructure.database.session import engine, Base
from backend.app.infrastructure.database.models import SourceModel, DocumentModel, PassageModel
from backend.app.domain.models.enums import SourceType
from backend.app.application.agents.philosophical_analyst import PhilosophicalAnalyst

@pytest.fixture
async def setup_test_env():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

@pytest.mark.asyncio
async def test_philosophical_analyst_reconstruction(setup_test_env):
    from backend.app.infrastructure.database.session import AsyncSessionLocal
    
    async with AsyncSessionLocal() as session:
        # 1. Setup prerequisite Source, Document, and Passage
        source = SourceModel(title="Nyayabhasya", author="Vatsyayana", source_type=SourceType.PRIMARY)
        session.add(source)
        await session.flush()

        doc = DocumentModel(source_id=source.id, checksum_sha256="phil_hash_789", mime_type="text/plain")
        session.add(doc)
        await session.flush()

        passage = PassageModel(document_id=doc.id, page_number=5, content="Pratyaksha is cognition resulting from sense-object connection.")
        session.add(passage)
        await session.commit()

        # 2. Run Philosophical Analyst
        analyst = PhilosophicalAnalyst(session)
        result = await analyst.reconstruct_argument(
            title="Validity of Perception in Nyaya",
            conclusion_statement="Perception is an infallible valid source of knowledge when conditions are met.",
            premises=[
                {
                    "statement": "Cognition arises directly from sense-object contact.",
                    "passage_id": passage.id,
                    "confidence": 0.98
                }
            ],
            assumptions=["Sense organs are functioning without defect."],
            original_terminology={"perception": "Pratyaksha", "cognition": "Jnana"}
        )

        # 3. Assertions & Checkpoints Verification
        assert result["argument_id"] is not None
        assert result["is_interpretation"] is True  # Marked as scholarly interpretation distinct from raw source
        assert result["original_terminology"]["perception"] == "Pratyaksha"
        assert len(result["premises"]) == 1
        assert result["premises"][0]["passage_id"] == passage.id

        # Safeguard: Verify unsupported premise reference fails
        with pytest.raises(ValueError, match="Philosophical analysis validation failed"):
            await analyst.reconstruct_argument(
                title="Invalid Argument",
                conclusion_statement="False",
                premises=[{"statement": "Unlinked premise", "passage_id": "non-existent-passage"}],
                assumptions=[]
            )