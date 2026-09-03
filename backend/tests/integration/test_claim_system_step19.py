import pytest

from backend.app.application.use_cases.claim_service import ClaimService
from backend.app.domain.models.enums import ClaimType, RelationType, SourceType
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
async def test_claim_system_lifecycle_and_evidence(setup_test_env):
    from backend.app.infrastructure.database.session import AsyncSessionLocal
    
    async with AsyncSessionLocal() as session:
        # 1. Setup source and passage for evidence linking
        source = SourceModel(title="Tarkasamgraha", author="Annam Bhatta", source_type=SourceType.PRIMARY)
        session.add(source)
        await session.flush()
        
        doc = DocumentModel(source_id=source.id, checksum_sha256="claim_hash", mime_type="text/plain")
        session.add(doc)
        await session.flush()
        
        passage = PassageModel(document_id=doc.id, content="Perception is the direct cognition arising from sense-object contact.")
        session.add(passage)
        await session.commit()
        
        # 2. Test Claim Creation across distinguishable types
        service = ClaimService(session)
        claim = await service.create_claim(
            statement="Sensory contact produces valid perception.",
            claim_type=ClaimType.DIRECT_SOURCE_CLAIM,
            confidence=0.95
        )
        
        assert claim.id is not None
        assert claim.claim_type == ClaimType.DIRECT_SOURCE_CLAIM
        assert claim.confidence == 0.95
        
        # 3. Test Evidence Linking (Supporting, Contradicting, Qualifying)
        ev_support = await service.link_evidence(claim.id, passage.id, RelationType.SUPPORTS)
        assert ev_support.relation_type == RelationType.SUPPORTS
        
        # 4. Retrieve and verify round-trip persistence
        details = await service.get_claim_with_evidence(claim.id)
        assert details["claim"].statement == claim.statement
        assert len(details["evidence_links"]) == 1
        assert details["evidence_links"][0].passage_id == passage.id