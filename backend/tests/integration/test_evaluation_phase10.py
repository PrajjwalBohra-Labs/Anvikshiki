import time
import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from backend.app.infrastructure.database.session import Base, get_db
from backend.app.infrastructure.database.models import SourceModel, DocumentModel, PassageModel
from backend.app.domain.models.enums import SourceType
from backend.app.main import app

@pytest.fixture
async def evaluation_db():
    test_engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async_session = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)

    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with async_session() as session:
        # Prepopulate with diverse domains: Classical Indian Epistemology & Cognitive Science
        s1 = SourceModel(
            title="Nyayavarttika of Uddyotakara",
            source_type=SourceType.PRIMARY,
            citation_string="Nyayavarttika 1.1.4",
            original_language="Sanskrit"
        )
        s2 = SourceModel(
            title="Journal of Cognitive Neuroscience",
            source_type=SourceType.SCIENTIFIC_STUDY,
            citation_string="J. Cog. Neuro. 2021",
            author="Miller et al."
        )
        session.add_all([s1, s2])
        await session.flush()

        d1 = DocumentModel(source_id=s1.id, file_path="nyaya.pdf", checksum_sha256="sha_nyaya", mime_type="application/pdf")
        d2 = DocumentModel(source_id=s2.id, file_path="cog_sci.pdf", checksum_sha256="sha_cog", mime_type="application/pdf")
        session.add_all([d1, d2])
        await session.flush()

        p1 = PassageModel(
            document_id=d1.id,
            page_number=12,
            content="Perception is cognition born of sense contact, unnamable and non-erroneous (avyabhicari).",
            source_type=SourceType.PRIMARY
        )
        p2 = PassageModel(
            document_id=d2.id,
            page_number=45,
            content="Visual perception shows neural predictive coding errors in low-contrast conditions.",
            source_type=SourceType.SCIENTIFIC_STUDY
        )
        session.add_all([p1, p2])
        await session.commit()
        yield session

    await test_engine.dispose()

@pytest.mark.asyncio
async def test_end_to_end_research_loop_benchmark(evaluation_db: AsyncSession):
    async def override_get_db():
        yield evaluation_db

    app.dependency_overrides[get_db] = override_get_db

    start_time = time.time()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        payload = {
            "user_id": "investigator_benchmark",
            "message": "Is visual perception (pratyaksha) non-erroneous under predictive coding?",
            "user_position": "Perception provides direct, infallible access to reality.",
            "confidence": 0.95
        }
        resp = await ac.post("/api/v1/dialogue/inquire", json=payload)

    elapsed = time.time() - start_time
    app.dependency_overrides.clear()

    assert resp.status_code == 200
    data = resp.json()

    # 1. Verification of Provenance & Reconstructed Arguments
    assert "inquiry_summary" in data
    assert len(data["arguments_examined"]) >= 1

    # 2. Challenger Node & Epistemic Boundaries
    assert "critical_challenges" in data
    assert data["unresolved_question"] is not None

    # 3. Latency Verification (Under 5.0 seconds for in-memory graph execution)
    assert elapsed < 5.0