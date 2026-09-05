from uuid import uuid4

import pytest
from sqlalchemy import delete, event

from backend.app.domain.models.enums import SourceType
from backend.app.infrastructure.ai.embedding_reranker_adapters import (
    LocalSentenceTransformerEmbeddingAdapter,
)
from backend.app.infrastructure.database.models import (
    DocumentModel,
    EvidenceLinkModel,
    PassageModel,
    SourceModel,
)
from backend.app.infrastructure.database.session import AsyncSessionLocal, engine
from backend.app.infrastructure.rag.semantic_retriever import SemanticRetriever

pytestmark = pytest.mark.postgres


@pytest.mark.asyncio
async def test_semantic_retriever_ranks_with_postgresql_cosine_distance() -> None:
    assert engine.dialect.name == "postgresql"
    await engine.dispose()

    embedder = LocalSentenceTransformerEmbeddingAdapter()
    target = "Direct perception arises from sense-object contact."
    distractor = "A recipe uses measured ingredients and controlled heat."
    vectors = await embedder.embed_texts([target, distractor])
    checksum = f"semantic-pgvector-{uuid4()}"

    statements: list[str] = []

    def capture_vector_sql(_conn, _cursor, statement, _parameters, _context, _executemany):
        if "<=>" in statement:
            statements.append(statement)

    async with AsyncSessionLocal() as session:
        source = SourceModel(title="Semantic pgvector source", source_type=SourceType.PRIMARY)
        session.add(source)
        await session.flush()
        document = DocumentModel(
            source_id=source.id,
            checksum_sha256=checksum,
            mime_type="text/plain",
        )
        session.add(document)
        await session.flush()
        passages = [
            PassageModel(document_id=document.id, content=target, embedding_model=embedder.model_version, embedding=vectors[0]),
            PassageModel(document_id=document.id, content=distractor, embedding_model=embedder.model_version, embedding=vectors[1]),
        ]
        session.add_all(passages)
        await session.commit()
        passage_ids = [passage.id for passage in passages]
        source_id = source.id
        document_id = document.id

    event.listen(engine.sync_engine, "before_cursor_execute", capture_vector_sql)
    try:
        async with AsyncSessionLocal() as session:
                results = await SemanticRetriever(session).search(
                    vectors[0], source_type=SourceType.PRIMARY, limit=2
                )

        assert statements, "SemanticRetriever did not execute PostgreSQL vector SQL"
        assert all("<=>" in statement for statement in statements)
        assert [result.passage.id for result in results] == [passage_ids[0], passage_ids[1]]
        assert results[0].score > results[1].score
    finally:
        event.remove(engine.sync_engine, "before_cursor_execute", capture_vector_sql)
        async with AsyncSessionLocal() as session:
            await session.execute(
                delete(EvidenceLinkModel).where(EvidenceLinkModel.passage_id.in_(passage_ids))
            )
            await session.execute(delete(PassageModel).where(PassageModel.document_id == document_id))
            await session.execute(delete(DocumentModel).where(DocumentModel.id == document_id))
            await session.execute(delete(SourceModel).where(SourceModel.id == source_id))
            await session.commit()
        await engine.dispose()
