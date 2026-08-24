import pytest
from backend.app.infrastructure.database.session import engine, Base
from backend.app.infrastructure.database.models import SourceModel, DocumentModel, PassageModel
from backend.app.domain.models.enums import SourceType, ClaimType, RelationType
from backend.app.application.agents.evidence_analyst import EvidenceAnalyst

@pytest.fixture
async def setup_test_env():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

@pytest.mark.asyncio
async def test_evidence_analyst_extraction_and_traceability(setup_test_env):
    from backend.app.infrastructure.database.session import AsyncSessionLocal
    
    async with AsyncSessionLocal() as session:
        # 1. Setup prerequisite Source, Document, and Passage
        source = SourceModel(title="Nyaya Sutra", author="Gotama", source_type=SourceType.PRIMARY)
        session.add(source)
        await session.flush()

        doc = DocumentModel(source_id=source.id, checksum_sha256="ev_hash_123", mime_type="text/plain")
        session.add(doc)
        await session.flush()

        passage = PassageModel(document_id=doc.id, page_number=12, content="Perception is non-erroneous cognition produced by sense contact.")
        session.add(passage)
        await session.commit()

        # 2. Run Evidence Analyst
        analyst = EvidenceAnalyst(session)
        result = await analyst.analyze_passage_evidence(
            passage_id=passage.id,
            claim_statement="Valid perception arises from sense-object contact.",
            claim_type=ClaimType.DIRECT_SOURCE_CLAIM,
            relation_type=RelationType.SUPPORTS,
            confidence_weight=0.95
        )

        # 3. Assertions & Checkpoints Verification
        assert result["claim_id"] is not None
        assert result["traceable"] is True
        assert result["passage_id"] == passage.id
        assert result["confidence"] == 0.95

        # Verify invalid/dangling passage reference raises error (no unsupported evidence)
        with pytest.raises(ValueError, match="Evidence validation failed"):
            await analyst.analyze_passage_evidence(
                passage_id="non-existent-passage-id",
                claim_statement="Unconnected claim"
            )