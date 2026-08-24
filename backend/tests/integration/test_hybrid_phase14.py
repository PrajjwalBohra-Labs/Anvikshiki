import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from backend.app.infrastructure.database.session import engine, Base
from backend.app.infrastructure.database.models import SourceModel, DocumentModel, PassageModel
from backend.app.domain.models.enums import SourceType
from backend.app.infrastructure.rag.retriever import HybridRetriever
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
async def test_hybrid_rag_fusion(setup_test_env):
    from backend.app.infrastructure.database.session import AsyncSessionLocal
    
    client = LocalEmbeddingClient()
    # Generate vector matching a semantic concept
    vec_concept = await client.get_embedding("The theory of inferential validation")

    async with AsyncSessionLocal() as session:
        src = SourceModel(title="Nyaya Texts", source_type=SourceType.PRIMARY)
        session.add(src)
        await session.flush()
        
        doc = DocumentModel(source_id=src.id, checksum_sha256="hybrid_hash", mime_type="text/plain")
        session.add(doc)
        await session.flush()
        
        # Passage 1: Matches exact lexical keyword 'anumana'
        p1 = PassageModel(document_id=doc.id, content="Anumana is secondary cognition.", embedding=await client.get_embedding("unrelated vector text"))
        
        # Passage 2: Matches semantic vector concept 'inferential validation'
        p2 = PassageModel(document_id=doc.id, content="Completely different wording about logic.", embedding=vec_concept)
        
        session.add_all([p1, p2])
        await session.commit()
        
        retriever = HybridRetriever(session, embedding_client=client)
        
        # Search query combines both lexical term ('anumana') and semantic theme ('theory of inferential validation')
        results = await retriever.hybrid_retrieve(query="anumana theory of inferential validation", top_k=2)
        
        # Both passages should be surfaced via RRF fusion
        assert len(results) == 2
        retrieved_ids = {r.passage.id for r in results}
        assert p1.id in retrieved_ids
        assert p2.id in retrieved_ids