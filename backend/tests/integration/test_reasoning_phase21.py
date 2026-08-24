import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from backend.app.infrastructure.database.session import engine, Base
from backend.app.infrastructure.database.models import SourceModel, DocumentModel, PassageModel
from backend.app.domain.models.enums import SourceType, PramanaType, EvidenceStatus
from backend.app.application.use_cases.reasoning_engine import ReasoningEngineService

@pytest.fixture
async def setup_test_env():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

@pytest.mark.asyncio
async def test_reasoning_engine_argument_synthesis(setup_test_env):
    from backend.app.infrastructure.database.session import AsyncSessionLocal
    
    async with AsyncSessionLocal() as session:
        # Seed test corpus
        source = SourceModel(title="Nyaya Karika", source_type=SourceType.PRIMARY)
        session.add(source)
        await session.flush()
        
        doc = DocumentModel(source_id=source.id, checksum_sha256="reasoning_hash", mime_type="text/plain")
        session.add(doc)
        await session.flush()
        
        passage = PassageModel(
            document_id=doc.id, 
            content="Where there is smoke, there is fire, just as in a hearth."
        )
        session.add(passage)
        await session.commit()
        
        # Execute Reasoning Engine
        engine_service = ReasoningEngineService(session)
        argument = await engine_service.synthesize_argument(query="smoke and fire inference")
        
        assert argument is not None
        assert argument.conclusion is not None
        assert len(argument.premises) == 1
        assert len(argument.evidence_links) == 1
        assert argument.pramana_type == PramanaType.ANUMANA
        assert argument.overall_status == EvidenceStatus.SUPPORTED
        assert argument.evidence_links[0].passage_id == passage.id