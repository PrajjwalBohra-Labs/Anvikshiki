import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from backend.app.infrastructure.database.session import engine, Base
from backend.app.infrastructure.database.models import SourceModel, DocumentModel, PassageModel
from backend.app.domain.models.enums import SourceType
from backend.app.application.use_cases.citation_service import CitationService
from backend.app.core.errors import AnvikshikiDomainError

@pytest.fixture
async def setup_test_env():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

@pytest.mark.asyncio
async def test_citation_generation_and_validation(setup_test_env):
    from backend.app.infrastructure.database.session import AsyncSessionLocal
    
    async with AsyncSessionLocal() as session:
        # 1. Setup Database state
        source = SourceModel(
            title="Tarka Sangraha", 
            author="Annam Bhatta", 
            source_type=SourceType.PRIMARY
        )
        fake_source = SourceModel(
            title="Hallucinated Source", 
            source_type=SourceType.UNVERIFIED
        )
        session.add_all([source, fake_source])
        await session.flush()
        
        doc = DocumentModel(source_id=source.id, checksum_sha256="hash1", mime_type="application/pdf")
        session.add(doc)
        await session.flush()
        
        passage = PassageModel(document_id=doc.id, content="Inference is the cause...", page_number=24)
        session.add(passage)
        await session.commit()
        
        service = CitationService(session)
        
        # 2. Test Format/Resolution
        citation = await service.generate_citation(passage.id)
        assert citation.passage_id == passage.id
        assert citation.source_id == source.id
        assert citation.citation_string == "Tarka Sangraha, by Annam Bhatta, p. 24"
        
        # 3. Test Validation Guardrail (Valid)
        is_valid = await service.validate_ai_citation(passage.id, source.id)
        assert is_valid is True
        
        # 4. Test Validation Guardrail (AI Hallucinated Source ID)
        is_invalid = await service.validate_ai_citation(passage.id, fake_source.id)
        assert is_invalid is False
        
        # 5. Test Nonexistent Passage
        with pytest.raises(AnvikshikiDomainError) as exc:
            await service.generate_citation("invalid_passage_uuid")
        assert exc.value.status_code == 404

@pytest.mark.asyncio
async def test_web_citation_formatting(setup_test_env):
    from backend.app.infrastructure.database.session import AsyncSessionLocal
    async with AsyncSessionLocal() as session:
        web_source = SourceModel(
            title="SEP: Epistemology in Classical Indian Philosophy",
            source_type=SourceType.DISCOVERY_ONLY,
            reference_url="https://plato.stanford.edu"
        )
        session.add(web_source)
        await session.flush()
        
        web_doc = DocumentModel(source_id=web_source.id, checksum_sha256="hash2", mime_type="text/html")
        session.add(web_doc)
        await session.flush()
        
        web_passage = PassageModel(document_id=web_doc.id, content="Web text...", page_number=None)
        session.add(web_passage)
        await session.commit()
        
        service = CitationService(session)
        citation = await service.generate_citation(web_passage.id)
        
        assert citation.citation_string == "SEP: Epistemology in Classical Indian Philosophy, (Retrieved from https://plato.stanford.edu)"