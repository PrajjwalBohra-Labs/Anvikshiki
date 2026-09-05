from unittest.mock import patch

import fitz
import pytest

from backend.app.application.use_cases.ingestion import DocumentIngestionService
from backend.app.domain.models.enums import SourceType
from backend.app.infrastructure.database.models import SourceModel
from backend.app.infrastructure.database.session import Base, engine
from backend.app.infrastructure.ocr.tesseract_service import TesseractOcrService


@pytest.fixture
async def setup_test_env(tmp_path, monkeypatch):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    
    from backend.app.core.config import settings
    monkeypatch.setattr(settings, "STORAGE_LOCAL_ROOT", str(tmp_path / "originals"))
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

def generate_blank_pdf() -> bytes:
    doc = fitz.open()
    doc.new_page()
    pdf_bytes = doc.write()
    doc.close()
    return pdf_bytes

def test_ocr_service_graceful_unavailable():
    with patch("pytesseract.get_tesseract_version", side_effect=FileNotFoundError):
        service = TesseractOcrService()
        assert service.is_available() is False

@pytest.mark.asyncio
@patch("backend.app.infrastructure.ocr.tesseract_service.TesseractOcrService.is_available", return_value=True)
@patch("backend.app.infrastructure.ocr.tesseract_service.TesseractOcrService.process_pdf_page")
async def test_ingestion_triggers_ocr_on_uncertainty(mock_process, mock_available, setup_test_env):
    # Mock OCR to return a low-confidence result
    mock_process.return_value = {
        "content": "Garbled text from bad scan...",
        "confidence": 0.45,  # Below 0.60 threshold
        "success": True
    }
    
    from backend.app.infrastructure.database.session import AsyncSessionLocal
    from backend.app.infrastructure.storage.local_storage import LocalStorageService
    storage = LocalStorageService()
    
    async with AsyncSessionLocal() as session:
        source = SourceModel(title="Scanned Paper", source_type=SourceType.SCIENTIFIC_STUDY)
        session.add(source)
        await session.commit()

        service = DocumentIngestionService(session, storage)
        pdf_bytes = generate_blank_pdf()  # Will trigger uncertainty heuristic (< 10 chars)
        
        doc, passages = await service.ingest_file(
            source_id=source.id,
            filename="scanned.pdf",
            content=pdf_bytes
        )
        
        # Verify OCR was called
        mock_process.assert_called_once()
        
        # Verify passage retained uncertainty because confidence (0.45) < 0.60
        assert passages[0].content == "Garbled text from bad scan..."
        assert passages[0].ocr_confidence == 0.45
        assert passages[0].extraction_uncertainty is True
