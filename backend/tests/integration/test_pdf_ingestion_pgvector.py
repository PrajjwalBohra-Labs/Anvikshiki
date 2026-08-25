from uuid import uuid4

import fitz
import pytest
from sqlalchemy import delete

from backend.app.application.use_cases.ingestion import DocumentIngestionService
from backend.app.core.config import settings
from backend.app.infrastructure.database.models import (
    DocumentModel,
    EvidenceLinkModel,
    PassageModel,
    SourceModel,
)
from backend.app.infrastructure.database.session import AsyncSessionLocal, engine
from backend.app.infrastructure.storage.local_storage import LocalStorageService


pytestmark = pytest.mark.postgres


def _make_text_pdf() -> bytes:
    document = fitz.open()
    page = document.new_page()
    page.insert_text((72, 72), "A real PDF page preserves its page number and source text.")
    payload = document.tobytes()
    document.close()
    return payload


@pytest.mark.asyncio
async def test_pdf_text_extraction_preserves_page_provenance_and_pgvector_embedding(tmp_path, monkeypatch) -> None:
    assert engine.dialect.name == "postgresql"
    monkeypatch.setattr(settings, "STORAGE_LOCAL_ROOT", str(tmp_path / "originals"))
    source_id = None
    document_id = None
    passage_ids: list[str] = []

    async with AsyncSessionLocal() as session:
        source = SourceModel(title=f"PDF pgvector source {uuid4()}")
        session.add(source)
        await session.flush()
        source_id = source.id

        document, passages = await DocumentIngestionService(
            session, LocalStorageService()
        ).ingest_file(source.id, "provenance.pdf", _make_text_pdf())
        document_id = document.id
        passage_ids = [passage.id for passage in passages]

        assert document.mime_type == "application/pdf"
        assert document.total_pages == 1
        assert passages
        assert passages[0].page_number == 1
        assert "real PDF page" in passages[0].content
        assert passages[0].embedding is not None
        assert len(passages[0].embedding) == 384
        assert passages[0].extraction_uncertainty is False

        await session.execute(delete(EvidenceLinkModel).where(EvidenceLinkModel.passage_id.in_(passage_ids)))
        await session.execute(delete(PassageModel).where(PassageModel.id.in_(passage_ids)))
        await session.execute(delete(DocumentModel).where(DocumentModel.id == document_id))
        await session.execute(delete(SourceModel).where(SourceModel.id == source_id))
        await session.commit()
