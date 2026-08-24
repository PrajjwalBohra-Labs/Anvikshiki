import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from backend.app.infrastructure.database.session import engine, Base
from backend.app.infrastructure.database.models import SourceModel, DocumentModel, PassageModel
from backend.app.domain.models.enums import SourceType
from backend.app.infrastructure.rag.reranker import AdvancedRetriever
from backend.app.infrastructure.llm.embedding_client import LocalEmbeddingClient

@pytest.fixture
async def setup_test_env():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

@pytest.mark.asyncio
async def test_advanced_retriever_with_reranking(setup_test_env):
    from backend.app.infrastructure.database.session import AsyncSessionLocal
    
    client = LocalEmbeddingClient()
    vec_generic = await client.get_embedding("General topic")

    async with AsyncSessionLocal() as session:
        src = SourceModel(title="Epistemology Texts", source_type=SourceType.PRIMARY)
        session.add(src)
        await session.flush()
        
        doc = DocumentModel(source_id=src.id, checksum_sha256="rerank_hash", mime_type="text/plain")
        session.add(doc)
        await session.flush()
        
        # Passage 1: Contains high query keyword overlap ("valid cognition")
        p1 = PassageModel(document_id=doc.id, content="Valid cognition is known as pramha and valid cognition is crucial.", embedding=vec_generic)
        # Passage 2: Low keyword overlap
        p2 = PassageModel(document_id=doc.id, content="Unrelated introductory remarks about general topics.", embedding=vec_generic)
        
        session.add_all([p1, p2])
        await session.commit()
        
        retriever = AdvancedRetriever(session, embedding_client=client)
        
        # Execute retrieve and rerank pipeline
        results = await retriever.retrieve_and_rerank(query="valid cognition", top_k=2)
        
        assert len(results) == 2
        # Cross-encoder should promote the passage with direct term overlap to the top rank
        assert results[0].passage.id == p1.id
        assert results[0].score > results[1].score