from uuid import uuid4

import pytest
from sqlalchemy import delete, event

from backend.app.application.orchestration.research_workflow import (
    ResearchWorkflowEngine,
)
from backend.app.application.use_cases.hybrid_retrieval import HybridRetrievalService
from backend.app.infrastructure.ai.embedding_reranker_adapters import (
    LocalSentenceTransformerEmbeddingAdapter,
)
from backend.app.infrastructure.database.models import (
    DocumentModel,
    EvidenceLinkModel,
    PassageModel,
    SourceCriticismModel,
    SourceModel,
)
from backend.app.infrastructure.database.session import AsyncSessionLocal, engine

pytestmark = pytest.mark.postgres


@pytest.mark.asyncio
async def test_hybrid_retrieval_service_executes_postgresql_vector_channel() -> None:
    """Exercise the real service, models, SQLAlchemy session, and pgvector SQL."""
    assert engine.dialect.name == "postgresql"
    await engine.dispose()

    embedder = LocalSentenceTransformerEmbeddingAdapter()
    contents = [
        "Pratyaksha is direct perception arising from sense-object contact.",
        "Immediate awareness follows contact between a sense and an object.",
        "Cooking recipes use heat and measured ingredients.",
    ]
    vectors = await embedder.embed_texts(contents)
    checksum = f"application-pgvector-{uuid4()}"
    statements: list[str] = []

    def capture_vector_sql(_conn, _cursor, statement, _parameters, _context, _executemany):
        if "<=>" in statement:
            statements.append(statement)

    event.listen(engine.sync_engine, "before_cursor_execute", capture_vector_sql)
    try:
        async with AsyncSessionLocal() as session:
            source = SourceModel(title="Application pgvector source")
            session.add(source)
            await session.flush()
            document = DocumentModel(
                source_id=source.id,
                checksum_sha256=checksum,
                mime_type="text/plain",
            )
            session.add(document)
            await session.flush()
            session.add_all(
                [
                    PassageModel(
                        document_id=document.id,
                        content=content,
                        embedding_model=embedder.model_version,
                        embedding=vector,
                    )
                    for content, vector in zip(contents, vectors)
                ]
            )
            await session.commit()

            service = HybridRetrievalService(session)
            evidence = await service.retrieve_evidence(
                "How does perception arise from sense contact?",
                top_k=3,
            )

            assert evidence
            assert statements, "The application service did not execute pgvector SQL"
            assert all("<=>" in statement for statement in statements)
            assert any("vector" in candidate["retrieval_channels"] for candidate in evidence)
            assert all(candidate["embedding_model"] == embedder.model_version for candidate in evidence)
            assert any("Pratyaksha" in candidate["content"] for candidate in evidence)

            await session.delete(document)
            await session.delete(source)
            await session.commit()
    finally:
        event.remove(engine.sync_engine, "before_cursor_execute", capture_vector_sql)
        await engine.dispose()


@pytest.mark.asyncio
async def test_research_workflow_retrieval_node_executes_pgvector() -> None:
    """Exercise ResearchWorkflowEngine through its real retrieval node."""
    # The async test runner creates a fresh event loop per test; dispose the
    # global pool so an asyncpg connection is never reused across loops.
    await engine.dispose()
    embedder = LocalSentenceTransformerEmbeddingAdapter()
    marker = f"workflowtoken{uuid4().hex}"
    content = f"{marker} Direct perception arises from reliable sense-object contact and produces immediate cognition."
    vector = (await embedder.embed_texts([content]))[0]
    checksum = f"workflow-pgvector-{uuid4()}"
    thread_id = f"workflow-pgvector-{uuid4()}"
    statements: list[str] = []

    def capture_vector_sql(_conn, _cursor, statement, _parameters, _context, _executemany):
        if "<=>" in statement:
            statements.append(statement)

    async with AsyncSessionLocal() as session:
        source = SourceModel(title="Workflow pgvector source")
        session.add(source)
        await session.flush()
        document = DocumentModel(
            source_id=source.id,
            checksum_sha256=checksum,
            mime_type="text/plain",
        )
        session.add(document)
        await session.flush()
        passage = PassageModel(
            document_id=document.id,
            content=content,
            page_number=4,
            embedding_model=embedder.model_version,
            embedding=vector,
        )
        session.add(passage)
        await session.commit()
        passage_id = passage.id
        source_id = source.id
        document_id = document.id

    event.listen(engine.sync_engine, "before_cursor_execute", capture_vector_sql)
    try:
        workflow = ResearchWorkflowEngine()
        result = await workflow.execute_research(
            f"{marker} How does direct perception arise from sense contact?",
            "workflow-pgvector-user",
            thread_id=thread_id,
        )
        assert result["current_step"] == "validation_completed"
        assert result["retrieved_passages"]
        assert any(item["passage_id"] == passage_id for item in result["retrieved_passages"])
        assert result["extracted_claims"]
        assert result["criticisms"]
        assert result["objections"]
        assert statements, "ResearchWorkflowEngine retrieval did not execute pgvector SQL"
        assert all("<=>" in statement for statement in statements)
    finally:
        event.remove(engine.sync_engine, "before_cursor_execute", capture_vector_sql)
        async with AsyncSessionLocal() as session:
            await session.execute(
                delete(SourceCriticismModel).where(SourceCriticismModel.source_id == source_id)
            )
            await session.execute(
                delete(EvidenceLinkModel).where(EvidenceLinkModel.passage_id == passage_id)
            )
            await session.execute(
                delete(PassageModel).where(PassageModel.document_id == document_id)
            )
            await session.execute(delete(DocumentModel).where(DocumentModel.id == document_id))
            await session.execute(delete(SourceModel).where(SourceModel.id == source_id))
            await session.commit()
        await engine.dispose()
