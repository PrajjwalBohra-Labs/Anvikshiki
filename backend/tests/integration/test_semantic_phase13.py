import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from backend.app.infrastructure.database.session import engine, Base
from backend.app.infrastructure.database.models import SourceModel, DocumentModel, PassageModel
from backend.app.domain.models.enums import SourceType
from backend.app.infrastructure.rag.semantic_retriever import SemanticRetriever
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
async def test_semantic_search_and_filtering(setup_test_env):
    from backend.app.infrastructure.database.session import AsyncSessionLocal
    
    # Generate synthetic vectors for testing
    client = LocalEmbeddingClient()
    vec_concept = await client.get_embedding("Philosophy of mind and consciousness")
    vec_unrelated = await client.get_embedding("Agricultural statistics 1999")
    vec_query = await client.get_embedding("Philosophy of mind and consciousness") # Exact match to concept
    
    async with AsyncSessionLocal() as session:
        # --- Seed Data ---
        src_primary = SourceModel(title="Text A", source_type=SourceType.PRIMARY)
        src_science = SourceModel(title="Study B", source_type=SourceType.SCIENTIFIC_STUDY)
        session.add_all([src_primary, src_science])
        await session.flush()
        
        doc_p = DocumentModel(source_id=src_primary.id, checksum_sha256="hash1", mime_type="text/plain")
        doc_s = DocumentModel(source_id=src_science.id, checksum_sha256="hash2", mime_type="text/plain")
        session.add_all([doc_p, doc_s])
        await session.flush()
        
        # Passage 1: High relevance (Primary Text)
        p1 = PassageModel(document_id=doc_p.id, content="Mind content", embedding=vec_concept)
        # Passage 2: Low relevance (Scientific Study)
        p2 = PassageModel(document_id=doc_s.id, content="Agriculture content", embedding=vec_unrelated)
        # Passage 3: High relevance (Scientific Study)
        p3 = PassageModel(document_id=doc_s.id, content="Neurology of mind", embedding=vec_concept)
        
        session.add_all([p1, p2, p3])
        await session.commit()
        
        retriever = SemanticRetriever(session)
        
        # --- Test 1: Basic Semantic Retrieval and Scoring ---
        results = await retriever.search(vec_query)
        assert len(results) == 3
        # p1 and p3 should tie for top score (1.0 exact match to query vector)
        assert results[0].score > 0.99
        assert results[1].score > 0.99
        assert results[2].score < 0.5  # The unrelated agricultural vector should score lower
        
        # --- Test 2: Epistemic Source Type Filtering ---
        # Querying the exact same vector, but restricting to SCIENTIFIC_STUDY
        results_filtered = await retriever.search(vec_query, source_type=SourceType.SCIENTIFIC_STUDY)
        
        assert len(results_filtered) == 2
        
        # Ensure the Primary source (p1) was successfully excluded by the filter
        returned_passage_ids = [r.passage.id for r in results_filtered]
        assert p1.id not in returned_passage_ids
        assert p3.id in returned_passage_ids