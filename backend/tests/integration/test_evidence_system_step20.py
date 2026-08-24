import pytest
from backend.app.infrastructure.database.session import engine, Base
from backend.app.infrastructure.database.models import SourceModel, DocumentModel, PassageModel, ClaimModel
from backend.app.domain.models.enums import SourceType, ClaimType, RelationType
from backend.app.application.use_cases.evidence_service import EvidenceService

@pytest.fixture
async def setup_test_env():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

@pytest.mark.asyncio
async def test_evidence_system_relationships_and_provenance(setup_test_env):
    from backend.app.infrastructure.database.session import AsyncSessionLocal
    
    async with AsyncSessionLocal() as session:
        # 1. Setup Source, Document, Passage, and Claim
        source = SourceModel(title="Brahma Sutra Bhashya", author="Shankara", source_type=SourceType.PRIMARY)
        session.add(source)
        await session.flush()
        
        doc = DocumentModel(source_id=source.id, checksum_sha256="ev_hash", mime_type="text/plain")
        session.add(doc)
        await session.flush()
        
        passage = PassageModel(
            document_id=doc.id, 
            page_number=45,
            content="Brahman is the single immutable cause of the origin, sustenance, and dissolution of the universe."
        )
        session.add(passage)
        await session.flush()

        claim = ClaimModel(
            statement="Brahman is the sole material and efficient cause of the universe.",
            claim_type=ClaimType.DIRECT_SOURCE_CLAIM
        )
        session.add(claim)
        await session.commit()

        # 2. Test Evidence Service and Relationships (Support, Contradiction, Qualification)
        service = EvidenceService(session)
        
        # Support relation
        ev_support = await service.add_evidence_relation(
            claim_id=claim.id,
            passage_id=passage.id,
            relation_type=RelationType.SUPPORTS,
            confidence_weight=0.98
        )
        assert ev_support.relation_type == RelationType.SUPPORTS
        assert ev_support.confidence_weight == 0.98

        # Contradiction relation representation test
        ev_contradict = await service.add_evidence_relation(
            claim_id=claim.id,
            passage_id=passage.id,
            relation_type=RelationType.CONTRADICTS,
            confidence_weight=0.85
        )
        assert ev_contradict.relation_type == RelationType.CONTRADICTS

        # 3. Test Evidence -> Source Provenance Traceability
        trace = await service.trace_evidence_source(ev_support.id)
        assert trace["passage"].id == passage.id
        assert trace["document"].id == doc.id
        assert trace["source"].title == "Brahma Sutra Bhashya"
        assert trace["source"].author == "Shankara"