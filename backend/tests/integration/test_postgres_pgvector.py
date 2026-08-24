import pytest
import math
from typing import List
from backend.app.infrastructure.database.session import engine, Base
from backend.app.infrastructure.database.models import SourceModel, DocumentModel, PassageModel
from backend.app.domain.models.enums import SourceType
from backend.app.infrastructure.ai.embedding_reranker_adapters import (
    LocalSentenceTransformerEmbeddingAdapter, LocalCrossEncoderRerankerAdapter
)

def cosine_similarity(v1: List[float], v2: List[float]) -> float:
    dot = sum(a * b for a, b in zip(v1, v2))
    norm1 = math.sqrt(sum(a * a for a in v1))
    norm2 = math.sqrt(sum(b * b for b in v2))
    return dot / (norm1 * norm2) if norm1 and norm2 else 0.0

@pytest.fixture
async def setup_test_env():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

@pytest.mark.asyncio
async def test_live_postgres_vector_retrieval_and_reranking(setup_test_env):
    from backend.app.infrastructure.database.session import AsyncSessionLocal
    from sqlalchemy.future import select

    embedder = LocalSentenceTransformerEmbeddingAdapter(model_name="all-MiniLM-L6-v2")
    reranker = LocalCrossEncoderRerankerAdapter(model_name="ms-marco-MiniLM-L-6-v2")

    async with AsyncSessionLocal() as session:
        # 1. Insert Canonical Source and Document
        source = SourceModel(title="Nyāya Sūtras", author="Akṣapāda Gotama", source_type=SourceType.PRIMARY)
        session.add(source)
        await session.flush()

        doc = DocumentModel(source_id=source.id, checksum_sha256="pgv_sha_12345", mime_type="text/plain")
        session.add(doc)
        await session.flush()

        # 2. Insert Passages with Vector Embeddings
        texts = [
            "Pratyakṣa (perception) is knowledge produced by sense-organ contact with an object.",
            "Anumāna (inference) is knowledge preceded by valid perceptual cognition.",
            "Upamāna (analogy) is knowledge of an object based on similarity to known objects."
        ]
        vectors = await embedder.embed_texts(texts)

        for i, (text, vec) in enumerate(zip(texts, vectors)):
            passage = PassageModel(
                document_id=doc.id,
                page_number=i + 1,
                content=text,
                embedding_model=embedder.model_version,
                embedding=vec
            )
            session.add(passage)
        await session.commit()

        # 3. Vector Similarity Search
        query = "What constitutes direct perceptual valid cognition?"
        query_vec = (await embedder.embed_texts([query]))[0]

        stmt = select(PassageModel).where(PassageModel.document_id == doc.id)
        res = await session.execute(stmt)
        all_passages = res.scalars().all()

        scored_candidates = []
        for p in all_passages:
            sim = cosine_similarity(query_vec, p.embedding)
            scored_candidates.append((p, sim))

        # Sort descending by vector cosine similarity
        scored_candidates.sort(key=lambda x: x[1], reverse=True)
        top_passage, top_sim = scored_candidates[0]

        assert top_passage is not None
        assert top_passage.embedding_model == "all-MiniLM-L6-v2@v1.0"
        assert len(top_passage.embedding) == 384

        # 4. Hybrid Cross-Encoder Reranking
        candidate_texts = [c[0].content for c in scored_candidates]
        reranked = await reranker.rerank(query, candidate_texts, top_k=2)

        assert len(reranked) == 2
        assert "relevance_score" in reranked[0]
        assert reranked[0]["relevance_score"] >= reranked[1]["relevance_score"]

        # 5. Provenance Preservation
        assert top_passage.document_id == doc.id
        parent_doc = await session.get(DocumentModel, top_passage.document_id)
        assert parent_doc.source_id == source.id