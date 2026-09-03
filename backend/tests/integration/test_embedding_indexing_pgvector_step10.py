from uuid import uuid4

import pytest
from pgvector.sqlalchemy import Vector
from sqlalchemy import delete, text

from backend.app.application.use_cases.embedding_indexing import EmbeddingIndexService
from backend.app.infrastructure.ai.embedding_reranker_adapters import (
    LocalSentenceTransformerEmbeddingAdapter,
)
from backend.app.infrastructure.database.models import (
    DocumentModel,
    PassageModel,
    SourceModel,
)
from backend.app.infrastructure.database.session import AsyncSessionLocal, engine

pytestmark = pytest.mark.postgres


@pytest.mark.asyncio
async def test_real_model_persists_and_queries_pgvector(monkeypatch):
    assert engine.dialect.name == "postgresql"
    assert isinstance(PassageModel.__table__.c.embedding.type, Vector)
    assert PassageModel.__table__.c.embedding.type.dim == 384

    embedder = LocalSentenceTransformerEmbeddingAdapter()
    # Do not permit a test to turn missing local model files into a network
    # download. This remains a real-model test when the configured model is
    # available locally, and honestly skips when it is not.
    monkeypatch.setenv("HF_HUB_OFFLINE", "1")
    try:
        embedder._get_model()
    except Exception as exc:
        pytest.skip(f"Configured local embedding model is unavailable offline: {exc}")
    marker = uuid4().hex
    async with AsyncSessionLocal() as session:
        source = SourceModel(title=f"Step10 real source {marker}")
        session.add(source)
        await session.flush()
        document = DocumentModel(
            source_id=source.id,
            checksum_sha256=f"step10-{marker}",
            mime_type="text/plain",
            original_filename=f"step10-{marker}.txt",
            size_bytes=64,
            total_pages=1,
        )
        session.add(document)
        await session.flush()
        passage = PassageModel(
            document_id=document.id,
            page_number=1,
            passage_order=0,
            content="Pramana is a means of valid knowledge.",
        )
        session.add(passage)
        await session.commit()
        try:
            result = await EmbeddingIndexService(session, embedder).index_passage(
                passage.id
            )
            assert result is not None
            assert result.status.value == "INDEXED"
            await session.refresh(passage)
            assert passage.embedding is not None
            assert len(passage.embedding) == 384

            query_vector = (await embedder.embed_texts([passage.content]))[0]
            search_results = await EmbeddingIndexService(session, embedder).search(
                query_vector=query_vector, document_id=document.id, limit=1
            )
            assert [item.passage.id for item in search_results] == [passage.id]
            assert search_results[0].score == pytest.approx(1.0, abs=1e-5)
            status = await session.scalar(
                text(
                    "select embedding_status::text from passages where id = :passage_id"
                ),
                {"passage_id": passage.id},
            )
            assert status == "INDEXED"
        finally:
            await session.execute(delete(PassageModel).where(PassageModel.id == passage.id))
            await session.execute(delete(DocumentModel).where(DocumentModel.id == document.id))
            await session.execute(delete(SourceModel).where(SourceModel.id == source.id))
            await session.commit()
