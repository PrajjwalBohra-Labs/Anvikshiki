import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from backend.app.infrastructure.database.session import engine, Base
from backend.app.infrastructure.database.models import SourceModel, DocumentModel, PassageModel
from backend.app.domain.models.enums import SourceType
from backend.app.infrastructure.rag.reranker import AdvancedRetriever
from backend.app.infrastructure.llm.embedding_client import LocalEmbeddingClient

@pytest.fixture
async def evaluation_corpus():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
        
    from backend.app.infrastructure.database.session import AsyncSessionLocal
    async with AsyncSessionLocal() as session:
        # Benchmark Corpus representing classical Indian epistemology
        src_nyaya = SourceModel(title="Nyaya Sutras", source_type=SourceType.PRIMARY)
        src_mod = SourceModel(title="Modern Cognitive Study on Perception", source_type=SourceType.SCIENTIFIC_STUDY)
        session.add_all([src_nyaya, src_mod])
        await session.flush()
        
        doc1 = DocumentModel(source_id=src_nyaya.id, checksum_sha256="eval_hash_1", mime_type="application/pdf")
        doc2 = DocumentModel(source_id=src_mod.id, checksum_sha256="eval_hash_2", mime_type="application/pdf")
        session.add_all([doc1, doc2])
        await session.flush()
        
        p1 = PassageModel(
            document_id=doc1.id, 
            page_number=4,
            content="Pratyaksha (perception) is cognition produced by sense-object contact, which is non-erroneous."
        )
        p2 = PassageModel(
            document_id=doc2.id, 
            page_number=12,
            content="Predictive coding models demonstrate that visual perception involves top-down priors."
        )
        session.add_all([p1, p2])
        await session.commit()
        
    yield
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

@pytest.mark.asyncio
async def test_retrieval_benchmark_recall_and_ranking(evaluation_corpus):
    from backend.app.infrastructure.database.session import AsyncSessionLocal
    client = LocalEmbeddingClient()
    
    async with AsyncSessionLocal() as session:
        retriever = AdvancedRetriever(session, embedding_client=client)
        
        # Benchmark Query 1: Direct Classical Epistemology Query
        query_classical = "Is pratyaksha non-erroneous perception?"
        results = await retriever.retrieve_and_rerank(query=query_classical, top_k=2)
        
        assert len(results) > 0
        # The primary text containing 'pratyaksha' must be retrieved (Recall = 100%)
        top_passage = results[0].passage
        assert "Pratyaksha" in top_passage.content
        
        # Benchmark Query 2: Scientific Neuroscience Query
        query_science = "How do predictive coding models explain visual perception?"
        results_sci = await retriever.retrieve_and_rerank(query=query_science, top_k=2)
        
        assert len(results_sci) > 0
        top_sci_passage = results_sci[0].passage
        assert "Predictive coding" in top_sci_passage.content