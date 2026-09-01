import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from backend.app.application.use_cases.provenance import ProvenanceService
from backend.app.application.use_cases.research_run_service import ResearchRunService
from backend.app.domain.models.enums import ClaimType, RelationType, SourceType
from backend.app.infrastructure.database.models import (
    ClaimModel,
    DocumentModel,
    EvidenceLinkModel,
    PassageModel,
    SourceModel,
)
from backend.app.infrastructure.database.session import Base


@pytest.fixture
async def graph_session():
    isolated_engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    async_session = async_sessionmaker(isolated_engine, expire_on_commit=False)
    async with isolated_engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    async with async_session() as session:
        yield session
    await isolated_engine.dispose()


@pytest.mark.asyncio
async def test_step54_materializes_only_real_run_provenance_records(graph_session) -> None:
    session = graph_session
    source = SourceModel(title="Graph source", source_type=SourceType.PRIMARY)
    session.add(source)
    await session.flush()
    document = DocumentModel(
        source_id=source.id,
        checksum_sha256="step54-graph-checksum",
        mime_type="text/plain",
    )
    session.add(document)
    await session.flush()
    passage = PassageModel(
        document_id=document.id,
        content="A real evidence passage.",
        page_number=2,
    )
    session.add(passage)
    await session.flush()
    run = await ResearchRunService(session).create_run(
        "Graph verification run",
        user_id="graph-owner",
    )
    claim = ClaimModel(
        statement="The passage supports the graph contract.",
        claim_type=ClaimType.DIRECT_SOURCE_CLAIM,
        provenance_id=passage.id,
        research_run_id=run.id,
    )
    session.add(claim)
    await session.flush()
    session.add(
        EvidenceLinkModel(
            claim_id=claim.id,
            passage_id=passage.id,
            relation_type=RelationType.SUPPORTS,
        )
    )
    await session.commit()

    graph = await ProvenanceService(session).trace_run_graph(run.id)

    assert graph is not None
    assert {node["entity_id"] for node in graph["nodes"]} >= {
        run.id,
        source.id,
        document.id,
        passage.id,
        claim.id,
    }
    assert {node["node_type"] for node in graph["nodes"]} >= {
        "RESEARCH_RUN",
        "SOURCE",
        "DOCUMENT",
        "PASSAGE",
        "CLAIM",
        "EVIDENCE",
    }
    assert {edge["relationship_type"] for edge in graph["edges"]} >= {
        "CONTAINS",
        "PRODUCES",
        "CITES",
        "SUPPORTS",
    }
