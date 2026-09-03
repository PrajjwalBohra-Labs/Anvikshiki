from uuid import uuid4

import pytest
from sqlalchemy import delete, select

from backend.app.application.use_cases.ingestion import DocumentIngestionService
from backend.app.core.config import settings
from backend.app.infrastructure.ai.embedding_reranker_adapters import (
    LocalSentenceTransformerEmbeddingAdapter,
)
from backend.app.infrastructure.database.models import (
    DocumentModel,
    DocumentVersionModel,
    EvidenceLinkModel,
    PageModel,
    PassageModel,
    SourceModel,
)
from backend.app.infrastructure.database.session import AsyncSessionLocal, engine
from backend.app.infrastructure.storage.local_storage import LocalStorageService

pytestmark = pytest.mark.postgres


@pytest.mark.asyncio
async def test_text_ingestion_generates_and_persists_real_pgvector_embedding(tmp_path, monkeypatch) -> None:
    assert engine.dialect.name == "postgresql"
    monkeypatch.setattr(settings, "STORAGE_LOCAL_ROOT", str(tmp_path / "originals"))
    embedder = LocalSentenceTransformerEmbeddingAdapter()
    checksum_marker = uuid4().hex

    async with AsyncSessionLocal() as session:
        source = SourceModel(title="Ingestion pgvector source")
        session.add(source)
        await session.flush()
        service = DocumentIngestionService(session, LocalStorageService())
        document, passages = await service.ingest_file(
            source.id,
            f"ingestion-{checksum_marker}.txt",
            b"Direct perception arises from reliable sense-object contact.",
        )

        assert len(passages) == 1
        assert passages[0].embedding_model == embedder.model_version
        assert passages[0].embedding is not None
        assert len(passages[0].embedding) == 384
        assert document.total_pages == 1

        passage_id = passages[0].id
        document_id = document.id
        source_id = source.id
        await session.execute(delete(EvidenceLinkModel).where(EvidenceLinkModel.passage_id == passage_id))
        await session.execute(delete(PassageModel).where(PassageModel.id == passage_id))
        version_ids = (
            await session.scalars(
                select(DocumentVersionModel.id).where(
                    DocumentVersionModel.document_id == document_id
                )
            )
        ).all()
        await session.execute(delete(PageModel).where(PageModel.document_version_id.in_(version_ids)))
        await session.execute(
            delete(DocumentVersionModel).where(DocumentVersionModel.id.in_(version_ids))
        )
        await session.execute(delete(DocumentModel).where(DocumentModel.id == document_id))
        await session.execute(delete(SourceModel).where(SourceModel.id == source_id))
        await session.commit()
