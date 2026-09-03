from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete, select

from backend.app.application.use_cases.user_service import UserService
from backend.app.core.config import settings
from backend.app.domain.models.enums import ClaimType, RelationType, SourceType
from backend.app.infrastructure.database.models import (
    AuthSessionModel,
    ClaimModel,
    DocumentModel,
    EvidenceLinkModel,
    PassageModel,
    ProvenanceEdgeModel,
    ProvenanceNodeModel,
    ResearchQuestionModel,
    ResearchRunModel,
    ResearchStepModel,
    SourceModel,
    UserModel,
)
from backend.app.infrastructure.database.session import AsyncSessionLocal, Base, engine
from backend.app.main import app


@pytest.fixture
async def export_records():
    previous_auth_mode = settings.AUTH_MODE
    settings.AUTH_MODE = "required"
    # The fixture is independently runnable and does not rely on another
    # integration module having initialized the schema first.
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    suffix = uuid4().hex
    owner_username = f"step64-owner-{suffix}"
    other_username = f"step64-other-{suffix}"
    async with AsyncSessionLocal() as session:
        owner, owner_token = await UserService(session).create_user(owner_username)
        other, other_token = await UserService(session).create_user(other_username)

        question = ResearchQuestionModel(
            user_id=owner.id,
            main_question="Which evidence supports the export contract?",
            domain="Epistemology",
            subquestions=[],
            open_questions=[],
            research_status="ACTIVE",
            research_history=[],
        )
        source = SourceModel(title="Step64 source", source_type=SourceType.PRIMARY)
        session.add_all([question, source])
        await session.flush()
        document = DocumentModel(
            source_id=source.id,
            checksum_sha256=f"step64-{suffix}",
            mime_type="text/plain",
            original_filename="step64.txt",
        )
        session.add(document)
        await session.flush()
        passage = PassageModel(
            document_id=document.id,
            content="A persisted passage supports deterministic research export.",
            page_number=1,
            passage_order=0,
        )
        session.add(passage)
        await session.flush()

        populated_run = ResearchRunModel(
            user_id=owner.id,
            research_question_id=question.id,
            thread_id=f"step64-thread-{suffix}",
            query=question.main_question,
            domain="Epistemology",
            depth="standard",
            status="COMPLETED",
        )
        empty_run = ResearchRunModel(
            user_id=owner.id,
            query="A minimal persisted research record",
            domain="Epistemology",
            depth="standard",
            status="RUNNING",
        )
        session.add_all([populated_run, empty_run])
        await session.flush()
        session.add(
            ResearchStepModel(
                run_id=populated_run.id,
                step_name="retrieval",
                step_type="RETRIEVAL",
                status="SUCCESS",
                payload={"passage_id": passage.id},
            )
        )
        claim = ClaimModel(
            statement="The persisted passage supports deterministic research export.",
            claim_type=ClaimType.DIRECT_SOURCE_CLAIM,
            provenance_id=passage.id,
            research_run_id=populated_run.id,
            confidence=0.9,
            lifecycle_status="ACTIVE",
        )
        session.add(claim)
        await session.flush()
        session.add(
            EvidenceLinkModel(
                claim_id=claim.id,
                passage_id=passage.id,
                relation_type=RelationType.SUPPORTS,
                confidence_weight=0.9,
            )
        )
        await session.commit()
        ids = {
            "owner_id": owner.id,
            "other_id": other.id,
            "populated_run_id": populated_run.id,
            "empty_run_id": empty_run.id,
            "question_id": question.id,
            "source_id": source.id,
            "document_id": document.id,
            "passage_id": passage.id,
            "claim_id": claim.id,
        }

    try:
        yield {**ids, "owner_token": owner_token, "other_token": other_token}
    finally:
        async with AsyncSessionLocal() as session:
            entity_ids = [
                ids["populated_run_id"],
                ids["source_id"],
                ids["document_id"],
                ids["passage_id"],
                ids["claim_id"],
            ]
            node_ids = list(
                (
                    await session.execute(
                        select(ProvenanceNodeModel.id).where(
                            ProvenanceNodeModel.entity_id.in_(entity_ids)
                        )
                    )
                )
                .scalars()
                .all()
            )
            if node_ids:
                await session.execute(
                    delete(ProvenanceEdgeModel).where(
                        (ProvenanceEdgeModel.from_node_id.in_(node_ids))
                        | (ProvenanceEdgeModel.to_node_id.in_(node_ids))
                    )
                )
                await session.execute(
                    delete(ProvenanceNodeModel).where(ProvenanceNodeModel.id.in_(node_ids))
                )
            await session.execute(
                delete(EvidenceLinkModel).where(EvidenceLinkModel.claim_id == ids["claim_id"])
            )
            await session.execute(delete(ClaimModel).where(ClaimModel.id == ids["claim_id"]))
            await session.execute(
                delete(ResearchStepModel).where(
                    ResearchStepModel.run_id == ids["populated_run_id"]
                )
            )
            await session.execute(
                delete(ResearchRunModel).where(
                    ResearchRunModel.id.in_([ids["populated_run_id"], ids["empty_run_id"]])
                )
            )
            await session.execute(
                delete(ResearchQuestionModel).where(
                    ResearchQuestionModel.id == ids["question_id"]
                )
            )
            await session.execute(delete(PassageModel).where(PassageModel.id == ids["passage_id"]))
            await session.execute(delete(DocumentModel).where(DocumentModel.id == ids["document_id"]))
            await session.execute(delete(SourceModel).where(SourceModel.id == ids["source_id"]))
            await session.execute(
                delete(AuthSessionModel).where(
                    AuthSessionModel.user_id.in_([ids["owner_id"], ids["other_id"]])
                )
            )
            await session.execute(
                delete(UserModel).where(UserModel.id.in_([ids["owner_id"], ids["other_id"]]))
            )
            await session.commit()
        settings.AUTH_MODE = previous_auth_mode


async def _client() -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


@pytest.mark.asyncio
async def test_export_is_authoritative_deterministic_and_preserves_provenance(export_records):
    async with await _client() as client:
        headers = {"Authorization": f"Bearer {export_records['owner_token']}"}
        first = await client.get(
            f"/api/v1/research/runs/{export_records['populated_run_id']}/export",
            headers=headers,
        )
        second = await client.get(
            f"/api/v1/research/runs/{export_records['populated_run_id']}/export?format=json",
            headers=headers,
        )
        empty = await client.get(
            f"/api/v1/research/runs/{export_records['empty_run_id']}/export",
            headers=headers,
        )

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json() == second.json()
    payload = first.json()
    assert payload["schema_version"] == "1.0"
    assert payload["format"] == "json"
    assert payload["research_run"]["run_id"] == export_records["populated_run_id"]
    assert payload["claims"][0]["claim_id"] == export_records["claim_id"]
    assert payload["claims"][0]["evidence_links"][0]["passage_id"] == export_records["passage_id"]
    assert payload["provenance"][0]["source"]["source_id"] == export_records["source_id"]
    assert payload["provenance"][0]["passage"]["passage_id"] == export_records["passage_id"]
    assert empty.status_code == 200
    assert empty.json()["claims"] == []
    assert empty.json()["provenance"] == []


@pytest.mark.asyncio
async def test_export_requires_authentication_and_enforces_ownership(export_records):
    async with await _client() as client:
        unauthenticated = await client.get(
            f"/api/v1/research/runs/{export_records['populated_run_id']}/export"
        )
        other_user = await client.get(
            f"/api/v1/research/runs/{export_records['populated_run_id']}/export",
            headers={"Authorization": f"Bearer {export_records['other_token']}"},
        )
        overridden = await client.get(
            f"/api/v1/research/runs/{export_records['populated_run_id']}/export",
            params={"user_id": export_records["other_id"]},
            headers={"Authorization": f"Bearer {export_records['owner_token']}"},
        )

    assert unauthenticated.status_code == 401
    assert other_user.status_code == 404
    assert overridden.status_code == 403
    assert "traceback" not in other_user.text.lower()


@pytest.mark.asyncio
async def test_export_rejects_unsupported_formats_and_invalid_records(export_records):
    async with await _client() as client:
        unsupported = await client.get(
            f"/api/v1/research/runs/{export_records['populated_run_id']}/export",
            params={"format": "csv"},
            headers={"Authorization": f"Bearer {export_records['owner_token']}"},
        )
        missing = await client.get(
            "/api/v1/research/runs/not-a-valid-persisted-record/export",
            headers={"Authorization": f"Bearer {export_records['owner_token']}"},
        )

    assert unsupported.status_code == 422
    assert missing.status_code == 404
    assert "internal" not in unsupported.text.lower()
