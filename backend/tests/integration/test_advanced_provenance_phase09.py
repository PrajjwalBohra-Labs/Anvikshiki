from hashlib import sha256
from pathlib import Path
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select

from backend.app.application.use_cases.ingestion import DocumentIngestionService
from backend.app.application.use_cases.provenance import ProvenanceService
from backend.app.application.use_cases.user_service import UserService
from backend.app.core.config import settings
from backend.app.domain.models.enums import ClaimType, RelationType, SourceType
from backend.app.infrastructure.ai.embedding_reranker_adapters import (
    LocalSentenceTransformerEmbeddingAdapter,
)
from backend.app.infrastructure.database.models import (
    ArgumentModel,
    ClaimModel,
    DocumentModel,
    DocumentVersionModel,
    EvidenceLinkModel,
    PageModel,
    PassageModel,
    PremiseModel,
    ProvenanceEdgeModel,
    ProvenanceNodeModel,
    ResearchRunModel,
    SourceModel,
)
from backend.app.infrastructure.database.session import AsyncSessionLocal, Base, engine
from backend.app.infrastructure.ocr.tesseract_service import TesseractOcrService
from backend.app.infrastructure.storage.local_storage import LocalStorageService
from backend.app.main import app


@pytest.fixture
async def provenance_environment(tmp_path, monkeypatch):
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.drop_all)
        await connection.run_sync(Base.metadata.create_all)

    monkeypatch.setattr(settings, "STORAGE_LOCAL_ROOT", str(tmp_path / "originals"))
    monkeypatch.setattr(
        LocalSentenceTransformerEmbeddingAdapter,
        "embed_texts",
        lambda self, texts: _fake_embeddings(texts),
    )
    monkeypatch.setattr(TesseractOcrService, "is_available", lambda self: False)
    previous_auth_mode = settings.AUTH_MODE
    settings.AUTH_MODE = "required"
    yield
    settings.AUTH_MODE = previous_auth_mode

    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.drop_all)


async def _fake_embeddings(texts):
    return [[0.0] * 384 for _ in texts]


async def _seed_document_chain(session):
    checksum = sha256(uuid4().bytes).hexdigest()
    source = SourceModel(
        title="Provenance test source",
        author="Test author",
        source_type=SourceType.PRIMARY,
        original_language="en",
    )
    session.add(source)
    await session.flush()
    document = DocumentModel(
        source_id=source.id,
        checksum_sha256=checksum,
        mime_type="application/pdf",
        total_pages=1,
        original_filename="provenance.pdf",
        storage_path=f"data/originals/{checksum}_provenance.pdf",
        size_bytes=42,
        extraction_method="pymupdf_text",
        extraction_status="success",
    )
    session.add(document)
    await session.flush()
    version = DocumentVersionModel(
        document_id=document.id,
        version_number=1,
        checksum_sha256=checksum,
        original_filename=document.original_filename,
        mime_type=document.mime_type,
        storage_path=document.storage_path,
        size_bytes=document.size_bytes,
        extraction_method="pymupdf_text",
        extraction_status="success",
    )
    session.add(version)
    await session.flush()
    page = PageModel(
        document_version_id=version.id,
        page_number=7,
        page_order=0,
        extracted_text="A page of source text.",
        native_extracted_text="A page of source text.",
        extraction_method="pymupdf_text",
        extraction_status="success",
    )
    session.add(page)
    await session.flush()
    passage = PassageModel(
        document_id=document.id,
        document_version_id=version.id,
        page_id=page.id,
        page_number=page.page_number,
        passage_order=0,
        content="A page of source text.",
        extraction_method="pymupdf_text",
        language="en",
    )
    session.add(passage)
    await session.flush()
    return source, document, version, page, passage


@pytest.mark.asyncio
async def test_real_pdf_ancestry_is_materialized_and_idempotent(provenance_environment):
    pdf_candidates = sorted(Path("data/originals").glob("*_tarka_samgraha.pdf"))
    if not pdf_candidates:
        pytest.skip("The repository real PDF fixture is unavailable.")

    pdf_path = pdf_candidates[0]
    original = pdf_path.read_bytes()
    checksum = sha256(original).hexdigest()

    async with AsyncSessionLocal() as session:
        source = SourceModel(
            title="Tarka Samgraha",
            source_type=SourceType.PRIMARY,
            original_language="en",
        )
        session.add(source)
        await session.commit()
        document, passages = await DocumentIngestionService(
            session, LocalStorageService()
        ).ingest_file(source.id, pdf_path.name, original, "application/pdf")

        graph = await ProvenanceService(session).trace_passage(passages[0].id)
        assert graph is not None
        node_types = {node["node_type"] for node in graph["nodes"]}
        assert {"SOURCE", "DOCUMENT", "DOCUMENT_VERSION", "PAGE", "PASSAGE"} <= node_types
        assert any(
            node["node_type"] == "PAGE" and node["metadata"]["page_number"] == 1
            for node in graph["nodes"]
        )
        assert any(
            node["node_type"] == "PASSAGE"
            and node["metadata"]["extraction_method"] == "pymupdf_text"
            for node in graph["nodes"]
        )

        before_nodes = await session.scalar(select(func.count(ProvenanceNodeModel.id)))
        before_edges = await session.scalar(select(func.count(ProvenanceEdgeModel.id)))
        second_graph = await ProvenanceService(session).trace_passage(passages[0].id)
        after_nodes = await session.scalar(select(func.count(ProvenanceNodeModel.id)))
        after_edges = await session.scalar(select(func.count(ProvenanceEdgeModel.id)))

        assert second_graph is not None
        assert before_nodes == after_nodes
        assert before_edges == after_edges
        assert document.checksum_sha256 == checksum
        assert pdf_path.read_bytes() == original


@pytest.mark.asyncio
async def test_claim_evidence_specialist_validation_and_synthesis_graph(
    provenance_environment,
):
    async with AsyncSessionLocal() as session:
        source, _document, version, page, passage = await _seed_document_chain(session)
        run = ResearchRunModel(
            user_id="provenance-user",
            query="What does the source establish?",
            domain="Epistemology",
            status="COMPLETED",
            output_references={},
        )
        session.add(run)
        await session.flush()
        claim = ClaimModel(
            statement="The source establishes a traceable proposition.",
            claim_type=ClaimType.DIRECT_SOURCE_CLAIM,
            provenance_id=passage.id,
            research_run_id=run.id,
            confidence=0.9,
        )
        argument = ArgumentModel(
            title="Source argument",
            conclusion_statement="The proposition is traceable.",
        )
        session.add_all([claim, argument])
        await session.flush()
        premise = PremiseModel(
            argument_id=argument.id,
            statement="The source passage is preserved.",
            is_supported=True,
        )
        session.add(premise)
        await session.flush()
        evidence = EvidenceLinkModel(
            claim_id=claim.id,
            passage_id=passage.id,
            relation_type=RelationType.SUPPORTS,
            confidence_weight=0.9,
        )
        premise_evidence = EvidenceLinkModel(
            premise_id=premise.id,
            passage_id=passage.id,
            relation_type=RelationType.SUPPORTS,
            confidence_weight=0.8,
        )
        session.add_all([evidence, premise_evidence])
        run.output_references = {
            "final_response": "A traceable synthesis.",
            "validation_status": "APPROVED",
            "validated_claims_count": 1,
            "validation": {
                "status": "APPROVED",
                "validated_claims": [{"claim_id": claim.id, "status": "validated"}],
                "blocked_claims": [],
            },
            "specialist_analysis": {
                "philosophical_arguments": [{"argument_id": argument.id}]
            },
        }
        await session.commit()

        graph_rows = await ProvenanceService(session).trace_run(run.id)
        assert len(graph_rows) == 1
        graph = graph_rows[0]
        nodes = {node["node_type"] for node in graph["graph_nodes"]}
        relations = {edge["relationship_type"] for edge in graph["graph_edges"]}
        assert {
            "RESEARCH_RUN",
            "PASSAGE",
            "DOCUMENT",
            "DOCUMENT_VERSION",
            "PAGE",
            "CLAIM",
            "EVIDENCE",
            "SPECIALIST_ANALYSIS",
            "VALIDATION",
            "SYNTHESIS",
        } <= nodes
        assert {
            "CONTAINS",
            "HAS_VERSION",
            "SUPPORTS",
            "CITES",
            "DERIVES_FROM",
            "VALIDATED_BY",
            "CONTRIBUTES_TO",
            "PRODUCES",
            "HAS_ANALYSIS",
            "HAS_VALIDATION",
            "HAS_EVIDENCE",
            "VALIDATES",
        } <= relations

        claim_graph = await ProvenanceService(session).trace_claim(claim.id)
        assert claim_graph is not None
        assert any(node["entity_id"] == claim.id for node in claim_graph["nodes"])
        impact = await ProvenanceService(session).trace_source_impact(source_id=source.id)
        assert impact == {
            "passage_ids": [passage.id],
            "claim_ids": [claim.id],
            "research_run_ids": [run.id],
        }
        assert await ProvenanceService(session).trace_passage("missing-passage") is None
        assert await ProvenanceService(session).trace_claim("missing-claim") is None
        assert (
            await ProvenanceService(session).trace_source_impact(document_id="missing-document")
            is None
        )


@pytest.mark.asyncio
async def test_public_graph_is_additive_and_run_ownership_is_preserved(
    provenance_environment,
):
    async with AsyncSessionLocal() as session:
        owner, owner_token = await UserService(session).create_user("provenance_owner")
        other, other_token = await UserService(session).create_user("provenance_other")
        _source, _document, version, page, passage = await _seed_document_chain(session)
        run = ResearchRunModel(
            user_id=owner.id,
            query="Trace the source.",
            domain="Epistemology",
            status="COMPLETED",
            output_references={"final_response": "Traceable."},
        )
        session.add(run)
        await session.flush()
        claim = ClaimModel(
            statement="A source can be traced.",
            claim_type=ClaimType.DIRECT_SOURCE_CLAIM,
            research_run_id=run.id,
            provenance_id=passage.id,
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

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get(
            f"/api/v1/research/runs/{run.id}/provenance",
            headers={"Authorization": f"Bearer {owner_token}"},
        )
        assert response.status_code == 200
        payload = response.json()
        assert payload and payload[0]["graph_nodes"]
        assert payload[0]["graph_edges"]
        assert payload[0]["passage"]["document_version_id"] == version.id
        assert payload[0]["passage"]["page_id"] == page.id

        graph_response = await client.get(
            f"/api/v1/research/runs/{run.id}/provenance/graph",
            headers={"Authorization": f"Bearer {owner_token}"},
        )
        assert graph_response.status_code == 200
        assert graph_response.json()["nodes"]
        assert graph_response.json()["edges"]

        foreign = await client.get(
            f"/api/v1/research/runs/{run.id}/provenance",
            headers={"Authorization": f"Bearer {other_token}"},
        )
        assert foreign.status_code == 404
        missing = await client.get(f"/api/v1/research/runs/{run.id}/provenance")
        assert missing.status_code == 401

    assert owner.id != other.id
