from pathlib import Path

import pytest
from sqlalchemy import delete, select

from backend.app.application.use_cases.embedding_indexing import EmbeddingIndexService
from backend.app.application.use_cases.ingestion import DocumentIngestionService
from backend.app.core.config import settings
from backend.app.domain.models.enums import SourceType
from backend.app.infrastructure.ai.embedding_reranker_adapters import (
    LocalCrossEncoderRerankerAdapter,
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
from backend.app.infrastructure.rag.reranker import AdvancedRetriever, LocalRerankerClient
from backend.app.infrastructure.storage.local_storage import LocalStorageService


pytestmark = pytest.mark.postgres


@pytest.mark.asyncio
async def test_real_cross_encoder_reranks_real_hybrid_candidates(monkeypatch):
    assert engine.dialect.name == "postgresql"
    pdfs = sorted(Path("data/originals").glob("*_tarka_samgraha.pdf"))
    if not pdfs:
        pytest.skip("The repository's tarka_samgraha.pdf original is unavailable.")

    monkeypatch.setenv("HF_HUB_OFFLINE", "1")
    embedding_adapter = LocalSentenceTransformerEmbeddingAdapter()
    reranker_adapter = LocalCrossEncoderRerankerAdapter()
    try:
        embedding_adapter._get_model()
        reranker_adapter._get_model()
    except Exception as exc:
        pytest.skip(f"Configured local ranking models are unavailable offline: {exc}")

    raw = pdfs[0].read_bytes()
    source_id = document_id = version_id = None
    passage_ids: list[str] = []
    async with AsyncSessionLocal() as session:
        source = SourceModel(
            title="Real tarka_samgraha reranking verification",
            source_type=SourceType.PRIMARY,
        )
        session.add(source)
        await session.flush()
        document, passages = await DocumentIngestionService(
            session, LocalStorageService()
        ).ingest_file(
            source_id=source.id,
            filename="tarka_samgraha.pdf",
            content=raw,
            mime_type="application/pdf",
        )
        version = (
            await session.execute(
                select(DocumentVersionModel).where(
                    DocumentVersionModel.document_id == document.id
                )
            )
        ).scalars().one()
        await EmbeddingIndexService(session, embedding_adapter).index_passages(
            document_id=document.id, batch_size=8
        )
        await session.commit()
        source_id, document_id, version_id = source.id, document.id, version.id
        passage_ids = [passage.id for passage in passages]

    try:
        monkeypatch.setattr(settings, "RERANKER_ENABLED", True)
        async with AsyncSessionLocal() as session:
            before = await HybridRetriever(session).hybrid_retrieve_with_metadata(
                query="anumana",
                top_k=4,
                source_id=source_id,
                document_id=document_id,
                document_version_id=version_id,
            )
            assert before.results
            assert before.status == "complete"

            reranker = LocalRerankerClient()
            advanced = AdvancedRetriever(
                session,
                reranker_client=reranker,
            )
            after = await advanced.retrieve_and_rerank_with_metadata(
                query="anumana",
                top_k=2,
                source_id=source_id,
                document_id=document_id,
                document_version_id=version_id,
            )
            assert after.results
            assert after.status == "complete"
            assert all(item.rerank_score is not None for item in after.results)
            assert all(item.hybrid_score is not None for item in after.results)
            assert all(item.lexical_score is not None or item.semantic_score is not None for item in after.results)
            assert all(item.passage.id in passage_ids for item in after.results)
            assert all(item.passage.document.source.id == source_id for item in after.results)
            assert all(
                item.passage.id in {candidate.passage.id for candidate in before.results}
                for item in after.results
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
