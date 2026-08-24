import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from backend.app.infrastructure.database.session import Base, get_db
from backend.app.infrastructure.database.models import SourceModel, DocumentModel, PassageModel
from backend.app.domain.models.enums import SourceType
from backend.app.main import app

@pytest.fixture
async def async_test_db():
    test_engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async_session = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)

    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with async_session() as session:
        # Prepopulate test evidence
        src = SourceModel(
            title="Nyaya Sutra Translation",
            source_type=SourceType.TRANSLATION,
            citation_string="Nyaya Sutra 1.1",
            translator="E. Cowell",
            original_language="Sanskrit"
        )
        session.add(src)
        await session.flush()

        doc = DocumentModel(
            source_id=src.id,
            file_path="dummy.pdf",
            checksum_sha256="testsha256",
            mime_type="application/pdf"
        )
        session.add(doc)
        await session.flush()

        p = PassageModel(
            document_id=doc.id,
            page_number=3,
            content="Perception (pratyaksha) requires indriyartha sannikarsha without subjective delusion.",
            source_type=SourceType.TRANSLATION
        )
        session.add(p)
        await session.commit()
        yield session

    await test_engine.dispose()

@pytest.mark.asyncio
async def test_dialogue_inquire_api_flow(async_test_db: AsyncSession):
    async def override_get_db():
        yield async_test_db

    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        payload = {
            "user_id": "test_investigator",
            "message": "Is pratyaksha perception reliable?",
            "user_position": "It is completely infallible.",
            "confidence": 0.9
        }
        response = await ac.post("/api/v1/dialogue/inquire", json=payload)

    app.dependency_overrides.clear()

    assert response.status_code == 200
    data = response.json()
    assert "inquiry_summary" in data
    assert len(data["arguments_examined"]) >= 1
    assert "critical_challenges" in data
    assert data["unresolved_question"] is not None