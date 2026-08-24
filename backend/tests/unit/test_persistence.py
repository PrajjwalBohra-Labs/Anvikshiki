import pytest
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from backend.app.infrastructure.database.session import Base
from backend.app.infrastructure.database.models import SourceModel, DocumentModel, PassageModel, ClaimModel
from backend.app.infrastructure.database.repositories.source_repository import SourceRepository, PassageRepository
from backend.app.domain.models.enums import SourceType, ClaimType

@pytest.fixture
async def async_db_session():
    # In-memory SQLite async engine for isolated unit tests
    test_engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async_session = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)

    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with async_session() as session:
        yield session

    await test_engine.dispose()

@pytest.mark.asyncio
async def test_source_and_passage_lifecycle(async_db_session: AsyncSession):
    source_repo = SourceRepository(async_db_session)
    passage_repo = PassageRepository(async_db_session)

    # 1. Create Source
    source = SourceModel(
        title="Nyaya Sutras of Gautama",
        author="Aksapada Gautama",
        source_type=SourceType.PRIMARY,
        citation_string="Nyaya Sutras 1.1.1"
    )
    await source_repo.create(source)
    assert source.id is not None

    # 2. Attach Document
    doc = DocumentModel(
        source_id=source.id,
        file_path="data/originals/nyaya_sutras.pdf",
        checksum_sha256="abc123456789fakechecksum",
        mime_type="application/pdf",
        total_pages=50
    )
    async_db_session.add(doc)
    await async_db_session.flush()

    # 3. Create Passage with Provenance & Uncertainty Flag
    passage = PassageModel(
        document_id=doc.id,
        page_number=1,
        section_heading="Pramana Epistemology",
        content="Pratyaksha, anumana, upamana, shabda iti pramanani.",
        source_type=SourceType.PRIMARY,
        ocr_confidence=0.98,
        extraction_uncertainty=False
    )
    await passage_repo.create(passage)
    await async_db_session.commit()

    # 4. Verify Retrieval and Traceability
    fetched_passages = await passage_repo.get_by_document(doc.id)
    assert len(fetched_passages) == 1
    assert fetched_passages[0].source_type == SourceType.PRIMARY
    assert "Pratyaksha" in fetched_passages[0].content