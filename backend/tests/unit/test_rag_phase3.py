import pytest
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from backend.app.infrastructure.database.session import Base
from backend.app.infrastructure.database.models import SourceModel, DocumentModel, PassageModel
from backend.app.domain.models.enums import SourceType
from backend.app.infrastructure.rag.retriever import HybridRetriever

@pytest.fixture
async def async_db_session():
    test_engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async_session = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)

    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with async_session() as session:
        yield session

    await test_engine.dispose()

@pytest.mark.asyncio
async def test_hybrid_rag_retrieval(async_db_session: AsyncSession):
    # Setup test source and document
    source = SourceModel(
        title="Pramana Samuccaya",
        source_type=SourceType.PRIMARY,
        citation_string="Pramana Samuccaya Chap 1"
    )
    async_db_session.add(source)
    await async_db_session.flush()

    doc = DocumentModel(
        source_id=source.id,
        file_path="dummy.pdf",
        checksum_sha256="testsha256",
        mime_type="application/pdf"
    )
    async_db_session.add(doc)
    await async_db_session.flush()

    # Passages with targeted philosophical terms
    p1 = PassageModel(
        document_id=doc.id,
        page_number=1,
        content="Perception (pratyaksha) is direct cognition free from conceptual construction (kalpana).",
        source_type=SourceType.PRIMARY
    )
    p2 = PassageModel(
        document_id=doc.id,
        page_number=2,
        content="Inference (anumana) depends on prior perception and invariable concomitance (vyapti).",
        source_type=SourceType.PRIMARY
    )
    p3 = PassageModel(
        document_id=doc.id,
        page_number=3,
        content="Modern cognitive neuroscience maps neural correlates of perceptual decision making.",
        source_type=SourceType.SCIENTIFIC_STUDY
    )
    async_db_session.add_all([p1, p2, p3])
    await async_db_session.commit()

    retriever = HybridRetriever(async_db_session)
    results = await retriever.hybrid_retrieve(query="What is perception and pratyaksha?", top_k=2)

    assert len(results) > 0
    top_match = results[0]
    assert "pratyaksha" in top_match.passage.content.lower()
    assert top_match.rank_type == "HYBRID_RRF"
    assert top_match.passage.page_number == 1