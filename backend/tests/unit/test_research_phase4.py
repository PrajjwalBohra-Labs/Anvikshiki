import pytest
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from backend.app.infrastructure.database.session import Base
from backend.app.infrastructure.database.models import SourceModel, DocumentModel, PassageModel
from backend.app.domain.models.enums import SourceType, ClaimType, PramanaType
from backend.app.infrastructure.rag.scholarly_filter import ScholarlySourceFilter
from backend.app.application.use_cases.research_planner import ResearchPlanner
from backend.app.application.use_cases.conduct_research import ResearchCoordinator

@pytest.fixture
async def async_db_session():
    test_engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async_session = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)

    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with async_session() as session:
        yield session

    await test_engine.dispose()

def test_scholarly_filtering_rules():
    assert ScholarlySourceFilter.evaluate_url("https://plato.stanford.edu/entries/epistemology-india/") == SourceType.SCHOLARLY_SECONDARY
    assert ScholarlySourceFilter.evaluate_url("https://www.ncbi.nlm.nih.gov/pmc/articles/PMC12345/") == SourceType.SCIENTIFIC_STUDY
    assert ScholarlySourceFilter.evaluate_url("https://sanskritdocuments.org/doc_z_misc_major_works/nyayasutra.html") == SourceType.PRIMARY
    assert ScholarlySourceFilter.evaluate_url("https://twitter.com/someone/status/123456") is None
    assert ScholarlySourceFilter.evaluate_url("https://randomblog.com/post") == SourceType.DISCOVERY_ONLY

def test_query_decomposition():
    plan = ResearchPlanner.plan_query("Examine pratyaksha and perception in cognition")
    assert len(plan.sub_questions) >= 2
    assert plan.depth == "deep_investigation"
    domains = [sq.focus_domain for sq in plan.sub_questions]
    assert "epistemology" in domains
    assert "neuroscience" in domains

@pytest.mark.asyncio
async def test_conduct_research_and_evidence_extraction(async_db_session: AsyncSession):
    source = SourceModel(
        title="Nyaya Bhashya of Vatsyayana",
        source_type=SourceType.PRIMARY,
        citation_string="Nyaya Bhashya 1.1.3"
    )
    async_db_session.add(source)
    await async_db_session.flush()

    doc = DocumentModel(
        source_id=source.id,
        file_path="nyaya_bhashya.pdf",
        checksum_sha256="checksumbhashya",
        mime_type="application/pdf"
    )
    async_db_session.add(doc)
    await async_db_session.flush()

    p1 = PassageModel(
        document_id=doc.id,
        page_number=4,
        content="Pratyaksha is cognition produced through the contact of sense organ with its object (indriyartha sannikarsha).",
        source_type=SourceType.PRIMARY
    )
    async_db_session.add(p1)
    await async_db_session.commit()

    coordinator = ResearchCoordinator(async_db_session)
    result = await coordinator.conduct_research("How is pratyaksha validated?")

    assert len(result.claims) > 0
    top_claim = result.claims[0]
    assert top_claim.claim_type == ClaimType.DIRECT_SOURCE_CLAIM
    assert top_claim.pramana_type == PramanaType.PRATYAKSHA
    assert p1.id in top_claim.supporting_passage_ids