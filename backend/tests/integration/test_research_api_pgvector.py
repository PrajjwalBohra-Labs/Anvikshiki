from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete, event

from backend.app.application.use_cases.user_service import UserService
from backend.app.infrastructure.ai.embedding_reranker_adapters import (
    LocalSentenceTransformerEmbeddingAdapter,
)
from backend.app.infrastructure.database.models import (
    AuthSessionModel,
    ClaimModel,
    DocumentModel,
    EvidenceLinkModel,
    PassageModel,
    SourceCriticismModel,
    SourceModel,
    UserModel,
)
from backend.app.infrastructure.database.session import AsyncSessionLocal, engine
from backend.app.main import app

pytestmark = pytest.mark.postgres


@pytest.mark.asyncio
async def test_research_api_and_sse_execute_real_pgvector_workflow() -> None:
    assert engine.dialect.name == "postgresql"
    await engine.dispose()

    marker = f"apiworkflow{uuid4().hex}"
    content = (
        f"{marker} Direct perception arises from reliable sense-object contact "
        "and produces immediate cognition."
    )
    embedder = LocalSentenceTransformerEmbeddingAdapter()
    vector = (await embedder.embed_texts([content]))[0]
    checksum = f"api-pgvector-{uuid4()}"
    statements: list[str] = []
    user_id = ""
    access_token = ""

    def capture_vector_sql(_conn, _cursor, statement, _parameters, _context, _executemany):
        if "<=>" in statement:
            statements.append(statement)

    async with AsyncSessionLocal() as session:
        user, access_token = await UserService(session).create_user(f"api-pgvector-{uuid4().hex}")
        user_id = user.id
        source = SourceModel(title="Research API pgvector source")
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
            page_number=7,
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
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/api/v1/research/run",
                json={
                    "user_id": user_id,
                    "query": f"{marker} How does direct perception arise from sense contact?",
                    "domain": "Epistemology",
                },
                headers={"Authorization": f"Bearer {access_token}"},
            )
            assert response.status_code == 200
            payload = response.json()
            assert payload["status"] in {"APPROVED", "BLOCKED_OR_DOWNGRADED"}
            assert payload["retrieved_passages_count"] > 0
            assert payload["safe_events"]

            stream_response = await client.post(
                "/api/v1/research/run/stream",
                json={
                    "user_id": user_id,
                    "query": f"{marker} stream direct perception",
                    "domain": "Epistemology",
                },
                headers={"Authorization": f"Bearer {access_token}"},
            )
            assert stream_response.status_code == 200
            assert "text/event-stream" in stream_response.headers["content-type"]
            assert "research_started" in stream_response.text
            assert "research_completed" in stream_response.text

        assert statements, "Research API did not execute PostgreSQL vector SQL"
        assert all("<=>" in statement for statement in statements)
    finally:
        event.remove(engine.sync_engine, "before_cursor_execute", capture_vector_sql)
        async with AsyncSessionLocal() as session:
            await session.execute(delete(EvidenceLinkModel).where(EvidenceLinkModel.passage_id == passage_id))
            await session.execute(delete(ClaimModel).where(ClaimModel.provenance_id == passage_id))
            await session.execute(delete(SourceCriticismModel).where(SourceCriticismModel.source_id == source_id))
            await session.execute(delete(PassageModel).where(PassageModel.document_id == document_id))
            await session.execute(delete(DocumentModel).where(DocumentModel.id == document_id))
            await session.execute(delete(SourceModel).where(SourceModel.id == source_id))
            await session.execute(delete(AuthSessionModel).where(AuthSessionModel.user_id == user_id))
            await session.execute(delete(UserModel).where(UserModel.id == user_id))
            await session.commit()
        await engine.dispose()
