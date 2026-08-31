from uuid import uuid4
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete, event, or_, select, text

from backend.app.application.use_cases.ingestion import DocumentIngestionService
from backend.app.main import app
from backend.app.domain.models.enums import SourceType
from backend.app.infrastructure.database.models import (
    DocumentModel,
    DocumentVersionModel,
    EvidenceLinkModel,
    PageModel,
    PassageModel,
    ProvenanceEdgeModel,
    ProvenanceNodeModel,
    SourceModel,
)
from backend.app.infrastructure.database.session import AsyncSessionLocal, engine
from backend.app.infrastructure.rag.lexical_retriever import LexicalRetriever
from backend.app.infrastructure.storage.local_storage import LocalStorageService


pytestmark = pytest.mark.postgres


@pytest.mark.asyncio
async def test_postgres_lexical_search_uses_tsvector_gin_and_preserves_identity():
    assert engine.dialect.name == "postgresql"
    checksum = f"lexical-pgvector-{uuid4()}"
    statements: list[str] = []

    def capture_sql(_conn, _cursor, statement, _parameters, _context, _executemany):
        if "search_vector" in statement or "websearch_to_tsquery" in statement:
            statements.append(statement)

    async with AsyncSessionLocal() as session:
        source = SourceModel(title="Real lexical source", source_type=SourceType.PRIMARY)
        session.add(source)
        await session.flush()
        document = DocumentModel(
            source_id=source.id,
            checksum_sha256=checksum,
            mime_type="text/plain",
            original_filename="lexical-real.txt",
            total_pages=1,
        )
        session.add(document)
        await session.flush()
        passages = [
            PassageModel(
                document_id=document.id,
                page_number=1,
                passage_order=0,
                content="Pratyaksha is direct perception and pratyaksha is non-erroneous.",
                extraction_method="utf8_text",
            ),
            PassageModel(
                document_id=document.id,
                page_number=2,
                passage_order=1,
                content="Inference is a distinct means of knowledge.",
                extraction_method="utf8_text",
            ),
        ]
        session.add_all(passages)
        await session.commit()
        passage_ids = [passage.id for passage in passages]
        source_id = source.id
        document_id = document.id

    event.listen(engine.sync_engine, "before_cursor_execute", capture_sql)
    try:
        async with AsyncSessionLocal() as session:
            retriever = LexicalRetriever(session)
            results = await retriever.search("pratyaksha", limit=5)
            assert [item.passage.id for item in results] == [passage_ids[0]]
            assert results[0].passage.page_number == 1
            assert results[0].passage.document.source.id == source_id
            assert results[0].score > 0

            filtered = await retriever.search("pratyaksha", document_id=document_id)
            assert [item.passage.id for item in filtered] == [passage_ids[0]]

            search_vector = await session.scalar(
                text("SELECT search_vector::text FROM passages WHERE id = :id"),
                {"id": passage_ids[0]},
            )
            assert "pratyaksha" in search_vector
            index_rows = (
                await session.execute(
                    text(
                        "SELECT indexname, indexdef FROM pg_indexes "
                        "WHERE tablename = 'passages' AND indexname = 'ix_passages_search_vector'"
                    )
                )
            ).all()
            assert len(index_rows) == 1
            assert "gin" in index_rows[0].indexdef.lower()

            passage = await session.get(PassageModel, passage_ids[0])
            passage.content = "Anumana is inference and vyapti is its necessary relation."
            await session.commit()
            refreshed_vector = await session.scalar(
                text("SELECT search_vector::text FROM passages WHERE id = :id"),
                {"id": passage_ids[0]},
            )
            assert "anumana" in refreshed_vector
            assert "pratyaksha" not in refreshed_vector
            await session.delete(passage)
            await session.commit()
            assert await session.scalar(
                text("SELECT COUNT(*) FROM passages WHERE id = :id"),
                {"id": passage_ids[0]},
            ) == 0
    finally:
        event.remove(engine.sync_engine, "before_cursor_execute", capture_sql)
        assert any("search_vector" in statement for statement in statements)
        assert any("websearch_to_tsquery" in statement for statement in statements)
        async with AsyncSessionLocal() as session:
            await session.execute(
                delete(EvidenceLinkModel).where(EvidenceLinkModel.passage_id.in_(passage_ids))
            )
            await session.execute(delete(PassageModel).where(PassageModel.document_id == document_id))
            await session.execute(delete(DocumentModel).where(DocumentModel.id == document_id))
            await session.execute(delete(SourceModel).where(SourceModel.id == source_id))
            await session.commit()


@pytest.mark.asyncio
async def test_lexical_search_api_contract_and_filters():
    checksum = f"lexical-api-{uuid4()}"
    async with AsyncSessionLocal() as session:
        source = SourceModel(title="Lexical API source", source_type=SourceType.PRIMARY)
        session.add(source)
        await session.flush()
        document = DocumentModel(
            source_id=source.id,
            checksum_sha256=checksum,
            mime_type="text/plain",
            original_filename="lexical-api.txt",
            total_pages=1,
        )
        session.add(document)
        await session.flush()
        passage = PassageModel(
            document_id=document.id,
            page_number=1,
            passage_order=0,
            content="Vyapti establishes the invariable relation used by inference.",
            extraction_method="utf8_text",
        )
        session.add(passage)
        await session.commit()
        source_id, document_id, passage_id = source.id, document.id, passage.id

    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(
                "/api/v1/search/",
                params={
                    "query": "vyapti",
                    "retrieval": "lexical",
                    "source_id": source_id,
                    "document_id": document_id,
                    "top_k": 1,
                },
            )
            assert response.status_code == 200
            payload = response.json()
            assert payload["total_results"] == 1
            result = payload["results"][0]
            assert result["passage_id"] == passage_id
            assert result["document_id"] == document_id
            assert result["source_id"] == source_id
            assert result["page_number"] == 1
            assert result["extraction_method"] == "utf8_text"
            assert result["retrieval_method"] == "lexical"
            assert result["relevance_score"] > 0
            assert "Lexical API source" in result["citation_string"]

            assert (await client.get(
                "/api/v1/search/", params={"query": "absent-term", "retrieval": "lexical"}
            )).json()["total_results"] == 0
            assert (await client.get(
                "/api/v1/search/", params={"query": "   ", "retrieval": "lexical"}
            )).status_code == 422
            assert (await client.get(
                "/api/v1/search/", params={"query": "x" * 1001, "retrieval": "lexical"}
            )).status_code == 422
    finally:
        async with AsyncSessionLocal() as session:
            await session.execute(
                delete(EvidenceLinkModel).where(EvidenceLinkModel.passage_id == passage_id)
            )
            await session.execute(delete(PassageModel).where(PassageModel.id == passage_id))
            await session.execute(delete(DocumentModel).where(DocumentModel.id == document_id))
            await session.execute(delete(SourceModel).where(SourceModel.id == source_id))
            await session.commit()


@pytest.mark.asyncio
async def test_real_tarka_samgraha_corpus_lexical_search():
    pdfs = sorted(Path("data/originals").glob("*_tarka_samgraha.pdf"))
    if not pdfs:
        pytest.skip("The repository's tarka_samgraha.pdf original is unavailable.")

    pdf_path = pdfs[0]
    pdf_content = pdf_path.read_bytes()
    source_id = document_id = None
    version_id = None
    passage_ids: list[str] = []
    async with AsyncSessionLocal() as session:
        source = SourceModel(
            title="Real tarka_samgraha corpus verification",
            source_type=SourceType.PRIMARY,
        )
        session.add(source)
        await session.flush()
        document, passages = await DocumentIngestionService(
            session, LocalStorageService()
        ).ingest_file(
            source_id=source.id,
            filename="tarka_samgraha.pdf",
            content=pdf_content,
            mime_type="application/pdf",
        )
        version = (
            await session.execute(
                select(DocumentVersionModel).where(
                    DocumentVersionModel.document_id == document.id
                )
            )
        ).scalars().one()
        source_id, document_id, version_id = source.id, document.id, version.id
        passage_ids = [passage.id for passage in passages]

    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(
                "/api/v1/search/",
                params={
                    "query": "anumana",
                    "retrieval": "lexical",
                    "source_id": source_id,
                    "document_id": document_id,
                    "document_version_id": version_id,
                    "source_type": "PRIMARY",
                },
            )
        assert response.status_code == 200
        payload = response.json()
        assert payload["total_results"] >= 1
        assert any(
            item["passage_id"] in passage_ids
            and "anumana" in item["content"].lower()
            and item["document_id"] == document_id
            and item["document_version_id"] == version_id
            and item["source_id"] == source_id
            for item in payload["results"]
        )
    finally:
        async with AsyncSessionLocal() as session:
            node_ids = (
                await session.execute(
                    select(ProvenanceNodeModel.id).where(
                        ProvenanceNodeModel.entity_id.in_(
                            [source_id, document_id, version_id, *passage_ids]
                        )
                    )
                )
            ).scalars().all()
            if node_ids:
                await session.execute(
                    delete(ProvenanceEdgeModel).where(
                        or_(
                            ProvenanceEdgeModel.from_node_id.in_(node_ids),
                            ProvenanceEdgeModel.to_node_id.in_(node_ids),
                        )
                    )
                )
                await session.execute(
                    delete(ProvenanceNodeModel).where(
                        ProvenanceNodeModel.id.in_(node_ids)
                    )
                )
            await session.execute(
                delete(EvidenceLinkModel).where(EvidenceLinkModel.passage_id.in_(passage_ids))
            )
            await session.execute(delete(PassageModel).where(PassageModel.id.in_(passage_ids)))
            await session.execute(delete(PageModel).where(PageModel.document_version_id == version_id))
            await session.execute(delete(DocumentVersionModel).where(DocumentVersionModel.id == version_id))
            await session.execute(delete(DocumentModel).where(DocumentModel.id == document_id))
            await session.execute(delete(SourceModel).where(SourceModel.id == source_id))
            await session.commit()
