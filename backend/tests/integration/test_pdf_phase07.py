import pytest
import fitz
from sqlalchemy.ext.asyncio import AsyncSession
from backend.app.infrastructure.database.session import engine, Base
from backend.app.infrastructure.database.models import SourceModel
from backend.app.infrastructure.storage.local_storage import LocalStorageService
from backend.app.application.use_cases.ingestion import DocumentIngestionService
from backend.app.domain.models.enums import SourceType

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

def generate_dummy_pdf() -> bytes:
    doc = fitz.open()
    
    # Page 1: Text
    page1 = doc.new_page()
    page1.insert_text((50, 50), "Pramana refers to the means of valid knowledge.")
    
    # Page 2: Blank/Scanned simulation (image but no text)
    page2 = doc.new_page()
    rect = fitz.Rect(100, 100, 200, 200)
    page2.draw_rect(rect, color=(0, 0, 0), fill=(0, 0, 0)) # Fake an image block
    
    pdf_bytes = doc.write()
    doc.close()
    return pdf_bytes

@pytest.mark.asyncio
async def test_pdf_ingestion_and_scanned_detection(setup_test_env):
    from backend.app.infrastructure.database.session import AsyncSessionLocal
    storage = LocalStorageService()
    
    async with AsyncSessionLocal() as session:
        # Create Source
        source = SourceModel(title="Epistemology Paper", source_type=SourceType.SCIENTIFIC_STUDY)
        session.add(source)
        await session.commit()

        # Ingest PDF
        service = DocumentIngestionService(session, storage)
        pdf_bytes = generate_dummy_pdf()
        
        doc, passages = await service.ingest_file(
            source_id=source.id,
            filename="paper.pdf",
            content=pdf_bytes
        )
        
        # Verify Document
        assert doc.mime_type == "application/pdf"
        assert doc.total_pages == 2
        
        # Verify Passages
        assert len(passages) >= 2
        
        # First page should have text and certainty
        p1 = next(p for p in passages if p.page_number == 1)
        assert "Pramana" in p1.content
        assert p1.extraction_uncertainty is False
        assert p1.ocr_confidence == 1.0
        
        # Second page should be flagged as uncertain (pending OCR)
        p2 = next(p for p in passages if p.page_number == 2)
        assert p2.extraction_uncertainty is True
        assert p2.ocr_confidence == 0.0