from hashlib import sha256
from pathlib import Path
from unittest.mock import patch

import fitz
import pytest
from sqlalchemy import func, select

from backend.app.application.use_cases.ingestion import DocumentIngestionService
from backend.app.core.errors import AnvikshikiDomainError
from backend.app.domain.models.enums import SourceType
from backend.app.infrastructure.ai.embedding_reranker_adapters import (
    LocalSentenceTransformerEmbeddingAdapter,
)
from backend.app.infrastructure.database.models import (
    DocumentModel,
    DocumentVersionModel,
    PageModel,
    SourceModel,
)
from backend.app.infrastructure.database.session import AsyncSessionLocal, Base, engine
from backend.app.infrastructure.storage.local_storage import LocalStorageService


@pytest.fixture
async def ingestion_environment(tmp_path, monkeypatch):
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.drop_all)
        await connection.run_sync(Base.metadata.create_all)

    from backend.app.core.config import settings

    monkeypatch.setattr(settings, "STORAGE_LOCAL_ROOT", str(tmp_path / "originals"))
    monkeypatch.setattr(
        LocalSentenceTransformerEmbeddingAdapter,
        "embed_texts",
        lambda self, texts: _fake_embed_texts(texts),
    )
    monkeypatch.setattr(
        "backend.app.infrastructure.ocr.tesseract_service.TesseractOcrService.is_available",
        lambda self: False,
    )
    yield

    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.drop_all)


async def _fake_embed_texts(texts):
    return [[0.0] * 384 for _ in texts]


def _make_pdf() -> bytes:
    document = fitz.open()
    first = document.new_page()
    first.insert_text((50, 50), "Pramana is a means of valid knowledge.")
    second = document.new_page()
    second.insert_text((50, 50), "Inference proceeds from a sign to what it indicates.")
    content = document.write()
    document.close()
    return content


async def _source_id(session) -> str:
    source = SourceModel(
        title="Local ingestion test source",
        source_type=SourceType.PRIMARY,
        original_language="en",
    )
    session.add(source)
    await session.commit()
    return source.id


@pytest.mark.asyncio
async def test_pdf_ingestion_preserves_pages_passages_and_original(ingestion_environment):
    content = _make_pdf()
    original_checksum = sha256(content).hexdigest()

    async with AsyncSessionLocal() as session:
        source_id = await _source_id(session)
        service = DocumentIngestionService(session, LocalStorageService())
        with patch(
            "backend.app.application.use_cases.ingestion.TesseractOcrService.process_pdf_page"
        ) as process_pdf_page:
            document, passages = await service.ingest_file(
                source_id, "knowledge.pdf", content, "application/pdf"
            )

        assert process_pdf_page.call_count == 0
        assert document.checksum_sha256 == original_checksum
        assert document.extraction_method == "pymupdf_text"
        assert document.extraction_status == "success"
        assert len(passages) == 2
        assert [passage.passage_order for passage in passages] == [0, 1]
        assert [passage.page_number for passage in passages] == [1, 2]
        assert all(passage.document_version_id for passage in passages)
        assert all(passage.page_id for passage in passages)

        version_result = await session.execute(
            select(DocumentVersionModel).where(DocumentVersionModel.document_id == document.id)
        )
        version = version_result.scalar_one()
        assert version.version_number == 1
        assert version.checksum_sha256 == original_checksum

        pages_result = await session.execute(
            select(PageModel)
            .where(PageModel.document_version_id == version.id)
            .order_by(PageModel.page_order)
        )
        pages = pages_result.scalars().all()
        assert [page.page_number for page in pages] == [1, 2]
        assert "Pramana" in pages[0].extracted_text
        assert "Inference" in pages[1].extracted_text

        stored = Path(document.storage_path)
        assert stored.read_bytes() == content
        assert sha256(stored.read_bytes()).hexdigest() == original_checksum


@pytest.mark.asyncio
async def test_markdown_and_plain_text_ingestion_preserve_order_and_sections(
    ingestion_environment,
):
    markdown = b"# Pramana\n\nA means of knowledge.\n\n## Inference\n\nA valid sign supports inference."
    plain_text = b"First paragraph.\n\nSecond paragraph."
    invalid_utf8 = b"A paragraph with an invalid byte: \xff"

    async with AsyncSessionLocal() as session:
        markdown_source_id = await _source_id(session)
        service = DocumentIngestionService(session, LocalStorageService())
        markdown_document, markdown_passages = await service.ingest_file(
            markdown_source_id, "notes.md", markdown, "text/markdown"
        )

        text_source_id = await _source_id(session)
        text_document, text_passages = await service.ingest_file(
            text_source_id, "notes.txt", plain_text, "text/plain"
        )
        warning_source_id = await _source_id(session)
        warning_document, _ = await service.ingest_file(
            warning_source_id, "warning.txt", invalid_utf8, "text/plain"
        )

        assert markdown_document.extraction_method == "markdown_text"
        assert [passage.passage_order for passage in markdown_passages] == [0, 1]
        assert [passage.section_heading for passage in markdown_passages] == [
            "Pramana",
            "Inference",
        ]
        assert [passage.content for passage in text_passages] == [
            "First paragraph.",
            "Second paragraph.",
        ]
        assert text_document.total_pages == 1
        assert all(passage.page_number == 1 for passage in text_passages)
        assert warning_document.extraction_status == "partial"
        assert "Invalid UTF-8 bytes were replaced." in warning_document.extraction_warnings


@pytest.mark.asyncio
async def test_duplicate_and_failed_ingestion_do_not_create_authoritative_records(
    ingestion_environment,
):
    content = b"A stable original document."
    invalid_pdf = b"not a PDF"

    async with AsyncSessionLocal() as session:
        source_id = await _source_id(session)
        service = DocumentIngestionService(session, LocalStorageService())
        await service.ingest_file(source_id, "stable.txt", content, "text/plain")

        with pytest.raises(AnvikshikiDomainError) as duplicate_error:
            await service.ingest_file(source_id, "renamed.txt", content, "text/plain")
        assert duplicate_error.value.status_code == 409

        with pytest.raises(AnvikshikiDomainError) as extraction_error:
            await service.ingest_file(source_id, "broken.pdf", invalid_pdf, "application/pdf")
        assert extraction_error.value.status_code == 422

        document_count = await session.scalar(select(func.count(DocumentModel.id)))
        version_count = await session.scalar(select(func.count(DocumentVersionModel.id)))
        assert document_count == 1
        assert version_count == 1


@pytest.mark.asyncio
async def test_unsupported_and_empty_documents_are_rejected(ingestion_environment):
    async with AsyncSessionLocal() as session:
        source_id = await _source_id(session)
        service = DocumentIngestionService(session, LocalStorageService())

        with pytest.raises(AnvikshikiDomainError) as unsupported_error:
            await service.ingest_file(source_id, "notes.docx", b"content", "application/msword")
        assert unsupported_error.value.status_code == 415

        with pytest.raises(AnvikshikiDomainError) as empty_error:
            await service.ingest_file(source_id, "empty.txt", b"  \n", "text/plain")
        assert empty_error.value.status_code == 422


@pytest.mark.asyncio
async def test_real_repository_pdf_and_text_are_ingested_without_modifying_originals(
    ingestion_environment,
):
    pdf_candidates = sorted(Path("data/originals").glob("*_tarka_samgraha.pdf"))
    text_candidates = sorted(Path("data/files/notes").glob("*_real_sample.txt"))
    if not pdf_candidates or not text_candidates:
        pytest.skip("Repository real-document fixtures are unavailable.")

    pdf_path = pdf_candidates[0]
    text_path = text_candidates[0]
    pdf_content = pdf_path.read_bytes()
    text_content = text_path.read_bytes()
    pdf_checksum = sha256(pdf_content).hexdigest()
    text_checksum = sha256(text_content).hexdigest()

    async with AsyncSessionLocal() as session:
        pdf_source_id = await _source_id(session)
        service = DocumentIngestionService(session, LocalStorageService())
        pdf_document, pdf_passages = await service.ingest_file(
            pdf_source_id, pdf_path.name, pdf_content, "application/pdf"
        )
        text_source_id = await _source_id(session)
        text_document, text_passages = await service.ingest_file(
            text_source_id, text_path.name, text_content, "text/plain"
        )

        assert pdf_document.checksum_sha256 == pdf_checksum
        assert pdf_document.total_pages == len(pdf_passages)
        assert pdf_passages
        assert all(passage.extraction_method == "pymupdf_text" for passage in pdf_passages)
        assert text_document.checksum_sha256 == text_checksum
        assert text_passages
        assert text_passages[0].content
        assert pdf_path.read_bytes() == pdf_content
        assert text_path.read_bytes() == text_content
