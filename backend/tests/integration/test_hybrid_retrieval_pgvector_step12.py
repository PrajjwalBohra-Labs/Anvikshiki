from pathlib import Path

import pytest
from sqlalchemy import delete, select

from backend.app.application.use_cases.embedding_indexing import EmbeddingIndexService
from backend.app.application.use_cases.ingestion import DocumentIngestionService
from backend.app.domain.models.enums import SourceType
from backend.app.infrastructure.ai.embedding_reranker_adapters import (
    LocalSentenceTransformerEmbeddingAdapter,
)
from backend.app.infrastructure.database.models import (
    DocumentModel,
    DocumentVersionModel,
    PageModel,
    PassageModel,
    ProvenanceEdgeModel,
    ProvenanceNodeModel,
    SourceModel,
)
from backend.app.infrastructure.database.session import AsyncSessionLocal, engine
from backend.app.infrastructure.rag.retriever import HybridRetriever
from backend.app.infrastructure.storage.local_storage import LocalStorageService

pytestmark = pytest.mark.postgres


@pytest.mark.asyncio
async def test_real_tarka_hybrid_uses_postgres_lexical_and_pgvector(monkeypatch):
    assert engine.dialect.name == "postgresql"
    pdfs = sorted(Path("data/originals").glob("*_tarka_samgraha.pdf"))
    if not pdfs:
        pytest.skip("The repository's tarka_samgraha.pdf original is unavailable.")
    pdf_path = pdfs[0]
    original_bytes = pdf_path.read_bytes()

    monkeypatch.setenv("HF_HUB_OFFLINE", "1")
    embedder = LocalSentenceTransformerEmbeddingAdapter()
    try:
        embedder._get_model()
    except Exception as exc:
        pytest.skip(f"Configured local embedding model is unavailable offline: {exc}")

    source_id = document_id = version_id = None
    passage_ids: list[str] = []
    async with AsyncSessionLocal() as session:
        source = SourceModel(
            title="Real tarka_samgraha hybrid verification",
            source_type=SourceType.PRIMARY,
        )
        session.add(source)
        await session.flush()
        document, passages = await DocumentIngestionService(
            session, LocalStorageService()
        ).ingest_file(
            source_id=source.id,
            filename="tarka_samgraha.pdf",
            content=original_bytes,
            mime_type="application/pdf",
        )
        version = (
            await session.execute(
                select(DocumentVersionModel).where(
                    DocumentVersionModel.document_id == document.id
                )
            )
        ).scalars().one()
        await EmbeddingIndexService(session, embedder).index_passages(
            document_id=document.id, batch_size=8
        )
        source_id, document_id, version_id = source.id, document.id, version.id
        passage_ids = [passage.id for passage in passages]
        await session.commit()

    try:
        async with AsyncSessionLocal() as session:
            outcome = await HybridRetriever(session).hybrid_retrieve_with_metadata(
                query="anumana",
                top_k=5,
                source_id=source_id,
                document_id=document_id,
                document_version_id=version_id,
            )
            assert outcome.status == "complete"
            assert outcome.lexical_count >= 1
            assert outcome.semantic_count >= 1
            assert outcome.results
            assert any(item.lexical_score is not None for item in outcome.results)
            assert any(item.semantic_score is not None for item in outcome.results)
            assert all(item.passage.id in passage_ids for item in outcome.results)
            assert all(item.passage.document.source.id == source_id for item in outcome.results)
            assert any("anumana" in item.passage.content.lower() for item in outcome.results)

            second = await HybridRetriever(session).hybrid_retrieve_with_metadata(
                query="anumana",
                top_k=5,
                source_id=source_id,
                document_id=document_id,
                document_version_id=version_id,
            )
            assert [item.passage.id for item in second.results] == [
                item.passage.id for item in outcome.results
            ]
            assert [item.hybrid_score for item in second.results] == [
                item.hybrid_score for item in outcome.results
            ]

            stored_original = Path(document.storage_path)
            assert stored_original.read_bytes() == original_bytes
            assert pdf_path.read_bytes() == original_bytes
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
                        (ProvenanceEdgeModel.from_node_id.in_(node_ids))
                        | (ProvenanceEdgeModel.to_node_id.in_(node_ids))
                    )
                )
                await session.execute(
                    delete(ProvenanceNodeModel).where(
                        ProvenanceNodeModel.id.in_(node_ids)
                    )
                )
            if passage_ids:
                await session.execute(
                    delete(PassageModel).where(PassageModel.id.in_(passage_ids))
                )
            if version_id:
                await session.execute(
                    delete(PageModel).where(PageModel.document_version_id == version_id)
                )
                await session.execute(
                    delete(DocumentVersionModel).where(
                        DocumentVersionModel.id == version_id
                    )
                )
            if document_id:
                await session.execute(
                    delete(DocumentModel).where(DocumentModel.id == document_id)
                )
            if source_id:
                await session.execute(delete(SourceModel).where(SourceModel.id == source_id))
            await session.commit()
