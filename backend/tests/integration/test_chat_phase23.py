import pytest

from backend.app.application.use_cases.chat_orchestrator import ChatOrchestratorService
from backend.app.domain.models.enums import SourceType
from backend.app.infrastructure.database.models import (
    DocumentModel,
    PassageModel,
    SourceModel,
    UserModel,
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
async def test_chat_orchestration_lifecycle(setup_test_env):
    from backend.app.infrastructure.database.session import AsyncSessionLocal
    
    async with AsyncSessionLocal() as session:
        # 1. Setup User and Corpus
        user = UserModel(username="scholar_one")
        source = SourceModel(title="Vedanta Sara", author="Sadananda", source_type=SourceType.PRIMARY)
        session.add_all([user, source])
        await session.flush()
        
        doc = DocumentModel(source_id=source.id, checksum_sha256="chat_hash", mime_type="text/plain")
        session.add(doc)
        await session.flush()
        
        passage = PassageModel(
            document_id=doc.id, 
            page_number=10,
            content="Ignorance (avidya) obscures the true nature of Atman."
        )
        session.add(passage)
        await session.commit()
        
        # 2. Execute Chat Orchestrator
        orchestrator = ChatOrchestratorService(session)
        response = await orchestrator.process_chat(
            user_id=user.id,
            conversation_id=None,
            message="What obscures the nature of Atman?"
        )
        
        assert response.conversation_id is not None
        assert "avidya" in response.reply
        assert len(response.citations) == 1
        assert "Vedanta Sara" in response.citations[0]
        assert response.argument_summary["pramana"] == "anumana"
        assert response.argument_summary["status"] == "supported"