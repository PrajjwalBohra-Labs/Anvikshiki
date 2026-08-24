import pytest
import io
import fitz
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from backend.app.infrastructure.database.session import Base
from backend.app.domain.models.enums import SourceType
from backend.app.application.use_cases.ingest_document import IngestionService

@pytest.fixture
async def async_db_session():
    test_engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async_session = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)

    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with async_session() as session:
        yield session

    await test_engine.dispose()

def generate_sample_pdf() -> bytes:
    doc = fitz.open()
    page1 = doc.new_page()
    page1.insert_text((50, 72), "Tarka Samgraha of Annambhatta: Prama is valid cognition.")
    page2 = doc.new_page()
    page2.insert_text((50, 72), "Anumana is the instrument of inferential knowledge (anumiti).")
    pdf_bytes = doc.tobytes()
    doc.close()
    return pdf_bytes

@pytest.mark.asyncio
async def test_pdf_ingestion_and_provenance(async_db_session: AsyncSession):
    service = IngestionService(async_db_session)
    pdf_bytes = generate_sample_pdf()

    doc, passages = await service.ingest_document(
        file_bytes=pdf_bytes,
        filename="tarka_samgraha.pdf",
        title="Tarka Samgraha",
        source_type=SourceType.PRIMARY,
        citation_string="Tarka Samgraha Deepika 1.1",
        author="Annambhatta"
    )

    assert doc.id is not None
    assert doc.total_pages == 2
    assert len(passages) == 2
    assert passages[0].page_number == 1
    assert "Tarka Samgraha" in passages[0].content
    assert passages[0].source_type == SourceType.PRIMARY
    assert passages[0].extraction_uncertainty is False
    assert passages[1].page_number == 2
    assert "Anumana" in passages[1].content