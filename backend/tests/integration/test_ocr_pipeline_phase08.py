from hashlib import sha256
from io import BytesIO
from pathlib import Path
import textwrap
from unittest.mock import patch

import fitz
import pytest
from sqlalchemy import select
from PIL import Image, ImageDraw, ImageFont

from backend.app.application.use_cases.ingestion import DocumentIngestionService
from backend.app.core.config import settings
from backend.app.domain.models.enums import SourceType
from backend.app.infrastructure.ai.embedding_reranker_adapters import (
    LocalSentenceTransformerEmbeddingAdapter,
)
from backend.app.infrastructure.database.models import PageModel, ProvenanceNodeModel, SourceModel
from backend.app.infrastructure.database.session import AsyncSessionLocal, Base, engine
from backend.app.infrastructure.ocr.tesseract_service import TesseractOcrService
from backend.app.infrastructure.storage.local_storage import LocalStorageService


@pytest.fixture
async def ocr_environment(tmp_path, monkeypatch):
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.drop_all)
        await connection.run_sync(Base.metadata.create_all)

    monkeypatch.setattr(settings, "STORAGE_LOCAL_ROOT", str(tmp_path / "originals"))
    monkeypatch.setattr(settings, "TEMPORARY_LOCAL_ROOT", str(tmp_path / "temporary"))
    monkeypatch.setattr(
        LocalSentenceTransformerEmbeddingAdapter,
        "embed_texts",
        lambda self, texts: _fake_embed_texts(texts),
    )
    yield

    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.drop_all)


async def _fake_embed_texts(texts):
    return [[0.0] * 384 for _ in texts]


def _pdf_with_text_and_blank_page() -> bytes:
    document = fitz.open()
    page = document.new_page()
    page.insert_text((50, 50), "Native text should remain authoritative.")
    document.new_page()
    content = document.write()
    document.close()
    return content


async def _source_id(session) -> str:
    source = SourceModel(title="OCR test source", source_type=SourceType.PRIMARY)
    session.add(source)
    await session.commit()
    return source.id


def test_ocr_configuration_is_local_and_bounded():
    assert isinstance(settings.OCR_LANGUAGES, str)
    assert settings.OCR_DPI >= 72
    assert settings.OCR_TIMEOUT_SECONDS > 0
    assert settings.OCR_TESSERACT_CMD is None or isinstance(settings.OCR_TESSERACT_CMD, str)


def test_missing_tesseract_is_an_explicit_failure():
    with patch(
        "backend.app.infrastructure.ocr.tesseract_service.pytesseract.get_tesseract_version",
        side_effect=FileNotFoundError,
    ):
        result = TesseractOcrService().process_pdf_page(b"not a pdf", 1)

    assert result["success"] is False
    assert result["status"] == "unavailable"
    assert result["content"] == ""
    assert "not available" in result["error"]


def test_unsupported_language_is_reported():
    service = TesseractOcrService()
    with (
        patch(
            "backend.app.infrastructure.ocr.tesseract_service.pytesseract.get_tesseract_version",
            return_value="5.0",
        ),
        patch(
            "backend.app.infrastructure.ocr.tesseract_service.pytesseract.get_languages",
            return_value=["eng"],
        ),
    ):
        error = service.availability_error("not-installed")

    assert error == "Unsupported OCR language(s): not-installed"


def test_language_is_selected_from_real_tesseract_candidate_scores():
    document = fitz.open()
    page = document.new_page()
    page.insert_text((50, 50), "English philosophical text")
    pdf_content = document.write()
    document.close()
    service = TesseractOcrService()
    with patch.object(service, "availability_error", return_value=None), patch(
        "backend.app.infrastructure.ocr.tesseract_service.pytesseract.image_to_data",
        side_effect=[
            {"text": ["garbled"], "conf": ["32"]},
            {"text": ["English"], "conf": ["94"]},
        ],
    ) as image_to_data:
        result = service.process_pdf_page(pdf_content, 1, language="deu+eng")

    assert result["language"] == "eng"
    assert result["confidence"] == pytest.approx(0.94)
    assert image_to_data.call_count == 2
    assert [call.kwargs["lang"] for call in image_to_data.call_args_list] == ["deu", "eng"]


def test_render_failure_is_structured():
    service = TesseractOcrService()
    with patch.object(service, "availability_error", return_value=None), patch(
        "backend.app.infrastructure.ocr.tesseract_service.fitz.open",
        side_effect=RuntimeError("corrupt PDF"),
    ):
        result = service.process_pdf_page(b"corrupt", 1)

    assert result["success"] is False
    assert result["status"] == "render_failed"
    assert result["content"] == ""
    assert "rendering failed" in result["error"]


def test_empty_ocr_result_is_structured():
    document = fitz.open()
    page = document.new_page()
    page.insert_text((50, 50), "An image-like page")
    pdf_content = document.write()
    document.close()
    service = TesseractOcrService()
    with patch.object(service, "availability_error", return_value=None), patch(
        "backend.app.infrastructure.ocr.tesseract_service.pytesseract.image_to_data",
        return_value={"text": [""], "conf": ["-1"]},
    ) as image_to_data:
        result = service.process_pdf_page(pdf_content, 1)

    assert result["success"] is False
    assert result["status"] == "empty"
    assert result["content"] == ""
    image_to_data.assert_called_once()
    assert image_to_data.call_args.kwargs["timeout"] == settings.OCR_TIMEOUT_SECONDS


@pytest.mark.asyncio
async def test_native_text_is_not_sent_to_ocr(ocr_environment):
    pdf_content = _pdf_with_text_and_blank_page()
    async with AsyncSessionLocal() as session:
        source_id = await _source_id(session)
        service = DocumentIngestionService(session, LocalStorageService())
        with patch.object(service.ocr_service, "is_available", return_value=True) as available, patch.object(
            service.ocr_service,
            "process_pdf_page",
            return_value={"success": False, "status": "empty", "content": "", "error": "empty"},
        ) as process_page:
            await service.ingest_file(source_id, "native.pdf", pdf_content, "application/pdf")

    available.assert_called_once()
    process_page.assert_called_once_with(
        pdf_content, 2, language=service.ocr_service.languages
    )


@pytest.mark.asyncio
async def test_ocr_fallback_preserves_page_and_passage_metadata(ocr_environment):
    pdf_content = _pdf_with_text_and_blank_page()
    original_checksum = sha256(pdf_content).hexdigest()
    ocr_result = {
        "success": True,
        "status": "success",
        "content": "Text recovered from the scanned page.",
        "confidence": 0.91,
        "language": "eng",
        "dpi": 300,
        "text_length": 37,
        "processed_at": "2026-08-29T00:00:00+00:00",
        "error": None,
    }

    async with AsyncSessionLocal() as session:
        source_id = await _source_id(session)
        service = DocumentIngestionService(session, LocalStorageService())
        with patch.object(service.ocr_service, "is_available", return_value=True), patch.object(
            service.ocr_service, "process_pdf_page", return_value=ocr_result
        ):
            document, passages = await service.ingest_file(
                source_id, "scanned.pdf", pdf_content, "application/pdf"
            )

        pages_result = await session.execute(
            select(PageModel).where(PageModel.document_version_id == passages[0].document_version_id)
        )
        pages = sorted(pages_result.scalars().all(), key=lambda page: page.page_order)
        ocr_page = pages[1]
        assert ocr_page.page_number == 2
        assert ocr_page.native_extracted_text == ""
        assert ocr_page.extracted_text == ocr_result["content"]
        assert ocr_page.extraction_method == "tesseract_ocr"
        assert ocr_page.ocr_status == "success"
        assert ocr_page.ocr_text_length == len(ocr_result["content"])
        assert ocr_page.ocr_text == ocr_result["content"]
        assert ocr_page.ocr_confidence == ocr_result["confidence"]
        assert passages[1].page_number == 2
        assert passages[1].extraction_method == "tesseract_ocr"
        assert passages[1].content == ocr_result["content"]
        assert document.extraction_status == "success"
        assert Path(document.storage_path).read_bytes() == pdf_content
        assert list(Path(settings.TEMPORARY_LOCAL_ROOT).iterdir()) == []
        assert document.checksum_sha256 == original_checksum


@pytest.mark.asyncio
async def test_ocr_failure_is_recorded_without_placeholder_text(ocr_environment):
    pdf_content = _pdf_with_text_and_blank_page()
    failure = {
        "success": False,
        "status": "timeout",
        "content": "",
        "confidence": 0.0,
        "language": "eng",
        "dpi": 300,
        "text_length": 0,
        "processed_at": "2026-08-29T00:00:00+00:00",
        "error": "Tesseract OCR timed out.",
    }

    async with AsyncSessionLocal() as session:
        source_id = await _source_id(session)
        service = DocumentIngestionService(session, LocalStorageService())
        with patch.object(service.ocr_service, "is_available", return_value=True), patch.object(
            service.ocr_service, "process_pdf_page", return_value=failure
        ):
            document, passages = await service.ingest_file(
                source_id, "timeout.pdf", pdf_content, "application/pdf"
            )

        pages_result = await session.execute(
            select(PageModel).where(PageModel.document_version_id == passages[0].document_version_id)
        )
        pages = sorted(pages_result.scalars().all(), key=lambda page: page.page_order)
        failed_page = pages[1]
        assert failed_page.ocr_status == "timeout"
        assert failed_page.ocr_error == failure["error"]
        assert failed_page.extraction_status == "partial"
        assert failed_page.extracted_text == ""
        assert passages[1].content == ""
        assert document.extraction_status == "partial"
        assert "timed out" in " ".join(document.extraction_warnings)


@pytest.mark.asyncio
async def test_low_confidence_ocr_is_stored_but_not_authoritative(ocr_environment):
    pdf_content = _pdf_with_text_and_blank_page()
    ocr_result = {
        "success": True,
        "status": "partial",
        "content": "Possibly garbled philosophical text.",
        "confidence": 0.45,
        "language": "eng",
        "dpi": 300,
        "text_length": 37,
        "processed_at": "2026-08-29T00:00:00+00:00",
        "error": None,
    }

    async with AsyncSessionLocal() as session:
        source_id = await _source_id(session)
        service = DocumentIngestionService(session, LocalStorageService())
        with patch.object(service.ocr_service, "is_available", return_value=True), patch.object(
            service.ocr_service, "process_pdf_page", return_value=ocr_result
        ):
            document, passages = await service.ingest_file(
                source_id, "low-confidence.pdf", pdf_content, "application/pdf"
            )

        pages_result = await session.execute(
            select(PageModel).where(PageModel.document_version_id == passages[0].document_version_id)
        )
        ocr_page = sorted(pages_result.scalars().all(), key=lambda page: page.page_order)[1]
        assert ocr_page.native_extracted_text == ""
        assert ocr_page.extracted_text == ""
        assert ocr_page.ocr_text == ocr_result["content"]
        assert ocr_page.ocr_confidence == ocr_result["confidence"]
        assert ocr_page.extraction_status == "partial"
        assert "not authoritative" in " ".join(ocr_page.extraction_warnings)
        assert passages[1].content == ocr_result["content"]
        assert passages[1].extraction_uncertainty is True
        assert passages[1].language == "eng"
        assert document.extraction_status == "partial"


def _difficult_philosophy_scan() -> bytes:
    excerpt = (
        "At every hour steadfastly resolve, as a Roman and a man, to do what is "
        "before thee with precise and unaffected dignity, with affection, freedom, "
        "and justice; and give thyself relief from all other thoughts. And thou wilt "
        "give thyself relief, if thou doest every act of thy life as if it were the "
        "last, laying aside every careless and vain thought, and all hypocrisy, and "
        "self-love, and discontent with the portion which has been given to thee."
    )
    width, height = 1800, 2400
    image = Image.new("L", (width, height), 247)
    draw = ImageDraw.Draw(image)
    font_paths = [
        Path("C:/Windows/Fonts/times.ttf"),
        Path("C:/Windows/Fonts/georgia.ttf"),
        Path("C:/Windows/Fonts/arial.ttf"),
    ]
    font_path = next(path for path in font_paths if path.exists())
    font = ImageFont.truetype(str(font_path), 48)
    draw.text((190, 150), "MEDITATIONS — BOOK II", fill=48, font=font)
    y = 300
    for line in textwrap.wrap(excerpt, width=62):
        draw.text((190, y), line, fill=40, font=font)
        y += 72
    # A slight skew, faded background, and lossy scan compression make this an
    # image-only difficult scan while retaining a legitimate source excerpt.
    image = image.rotate(1.2, resample=Image.Resampling.BICUBIC, expand=False, fillcolor=247)
    image_buffer = BytesIO()
    image.save(image_buffer, format="JPEG", quality=58, optimize=True)

    document = fitz.open()
    page = document.new_page(width=612, height=792)
    page.insert_image(page.rect, stream=image_buffer.getvalue())
    pdf_content = document.write()
    document.close()
    return pdf_content


@pytest.mark.asyncio
async def test_real_tesseract_difficult_philosophy_ingestion(ocr_environment):
    service = TesseractOcrService()
    if not service.is_available():
        pytest.skip(service.availability_error() or "Tesseract is unavailable")

    pdf_content = _difficult_philosophy_scan()
    original_checksum = sha256(pdf_content).hexdigest()
    async with AsyncSessionLocal() as session:
        source_id = await _source_id(session)
        ingestion = DocumentIngestionService(session, LocalStorageService())
        document, passages = await ingestion.ingest_file(
            source_id, "marcus-aurelius-scan.pdf", pdf_content, "application/pdf"
        )

        pages_result = await session.execute(
            select(PageModel).where(PageModel.document_version_id == passages[0].document_version_id)
        )
        page = pages_result.scalars().one()
        stored_pdf = Path(document.storage_path).read_bytes()

        assert page.page_number == 1
        assert page.ocr_status in {"success", "partial"}
        assert page.ocr_language == "eng"
        assert page.ocr_confidence is not None
        assert page.ocr_text_length == len(page.ocr_text or "")
        assert page.ocr_text
        assert passages[0].page_number == 1
        assert passages[0].extraction_method == "tesseract_ocr"
        assert passages[0].language == "eng"
        assert passages[0].ocr_confidence == pytest.approx(page.ocr_confidence)
        assert passages[0].extraction_uncertainty is (page.ocr_status == "partial")
        provenance_result = await session.execute(
            select(ProvenanceNodeModel).where(ProvenanceNodeModel.entity_id == page.id)
        )
        page_provenance = provenance_result.scalars().one()
        assert page_provenance.metadata_payload["page_number"] == 1
        assert page_provenance.metadata_payload["ocr_language"] == "eng"
        assert page_provenance.metadata_payload["ocr_confidence"] == pytest.approx(
            page.ocr_confidence
        )
        assert document.checksum_sha256 == original_checksum
        assert stored_pdf == pdf_content
        with fitz.open(stream=stored_pdf, filetype="pdf") as stored_document:
            assert stored_document.page_count == 1
        assert list(Path(settings.TEMPORARY_LOCAL_ROOT).iterdir()) == []
