import pytest
from httpx import ASGITransport, AsyncClient

from backend.app.domain.models.enums import ClaimType, RelationType, SourceType
from backend.app.infrastructure.database.models import (
    ClaimModel,
    DocumentModel,
    EvidenceLinkModel,
    PassageModel,
    ResearchRunModel,
    SourceModel,
    UserModel,
)
from backend.app.infrastructure.database.session import AsyncSessionLocal, Base, engine
from backend.app.application.use_cases.research_run_service import ResearchRunService
from backend.app.main import app


@pytest.fixture
async def setup_test_env():
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.drop_all)
        await connection.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.drop_all)


@pytest.mark.asyncio
async def test_public_run_history_result_claims_and_provenance(setup_test_env):
    async with AsyncSessionLocal() as session:
        user = UserModel(id="contract-user", username="contract_user")
        source = SourceModel(title="Contract Source", source_type=SourceType.PRIMARY)
        session.add_all([user, source])
        await session.flush()
        document = DocumentModel(
            source_id=source.id,
            checksum_sha256="contract-document-hash",
            mime_type="text/plain",
            original_filename="contract.txt",
        )
        session.add(document)
        await session.flush()
        passage = PassageModel(
            document_id=document.id,
            page_number=3,
            content="A contract passage with inspectable provenance.",
        )
        session.add(passage)
        await session.flush()
        run = ResearchRunModel(
            user_id=user.id,
            research_question_id=None,
            thread_id="contract-thread",
            query="What is inspectable evidence?",
            domain="Epistemology",
            depth="standard",
            status="COMPLETED",
            output_references={
                "run_id": "placeholder",
                "query": "What is inspectable evidence?",
                "domain": "Epistemology",
                "validation_status": "APPROVED",
                "final_response": "A result grounded in the contract passage.",
                "validated_claims_count": 1,
                "retrieved_passages": [{
                    "passage_id": passage.id,
                    "source_id": source.id,
                    "source_title": source.title,
                    "content": passage.content,
                    "page_number": 3,
                    "source_type": "PRIMARY",
                    "retrieval_channels": ["vector"],
                }],
                "claims": [{
                    "claim_id": "claim-placeholder",
                    "statement": "A contract passage can be inspected.",
                    "claim_type": "DIRECT_SOURCE_CLAIM",
                    "passage_id": passage.id,
                    "confidence": 0.95,
                }],
                "specialist_analysis": {"philosophical_arguments": [{"title": "Argument"}]},
                "validation": {"status": "APPROVED", "validated_claims": []},
            },
        )
        session.add(run)
        await session.flush()
        claim = ClaimModel(
            statement="A contract passage can be inspected.",
            claim_type=ClaimType.DIRECT_SOURCE_CLAIM,
            provenance_id=passage.id,
            research_run_id=run.id,
            confidence=0.95,
        )
        session.add(claim)
        await session.flush()
        link = EvidenceLinkModel(
            claim_id=claim.id,
            passage_id=passage.id,
            relation_type=RelationType.SUPPORTS,
            confidence_weight=0.95,
        )
        session.add(link)
        await session.commit()
        run_id = run.id
        document_id = document.id

        await ResearchRunService(session).record_event(
            run_id,
            {"event": "research_started", "run_id": run_id, "sequence": 1},
            1,
        )
        await ResearchRunService(session).record_event(
            run_id,
            {"event": "research_completed", "run_id": run_id, "sequence": 2},
            2,
        )
        await ResearchRunService(session).record_event(
            run_id,
            {"event": "research_completed", "run_id": run_id, "sequence": 2},
            2,
        )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        history = await client.get("/api/v1/research/runs", params={"user_id": "contract-user"})
        assert history.status_code == 200
        assert history.json()[0]["run_id"] == run_id

        detail = await client.get(f"/api/v1/research/runs/{run_id}", params={"user_id": "contract-user"})
        assert detail.status_code == 200
        assert detail.json()["result"]["validation_status"] == "APPROVED"
        assert len(detail.json()["steps"]) == 2
        assert detail.json()["steps"][0]["event_id"].startswith(run_id + ":")

        claims = await client.get(f"/api/v1/research/runs/{run_id}/claims", params={"user_id": "contract-user"})
        assert claims.status_code == 200
        assert claims.json()[0]["evidence_links"][0]["relation_type"] == "SUPPORTS"

        provenance = await client.get(f"/api/v1/research/runs/{run_id}/provenance", params={"user_id": "contract-user"})
        assert provenance.status_code == 200
        assert provenance.json()[0]["source"]["title"] == "Contract Source"
        assert provenance.json()[0]["document"]["document_id"] == document_id

        replay = await client.get(
            f"/api/v1/research/runs/{run_id}/events",
            params={"user_id": "contract-user"},
            headers={"Last-Event-ID": f"{run_id}:1"},
        )
        assert replay.status_code == 200
        assert f"id: {run_id}:2" in replay.text
        assert "research_completed" in replay.text

        forbidden = await client.get(f"/api/v1/research/runs/{run_id}", params={"user_id": "other-user"})
        assert forbidden.status_code == 404


@pytest.mark.asyncio
async def test_public_documents_identity_and_web_security(setup_test_env):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        created = await client.post("/api/v1/users", json={"username": "public_identity"})
        assert created.status_code == 201
        user_id = created.json()["user_id"]

        fetched = await client.get(f"/api/v1/users/{user_id}")
        assert fetched.status_code == 200
        assert fetched.json()["username"] == "public_identity"

        duplicate = await client.post("/api/v1/users", json={"username": "public_identity"})
        assert duplicate.status_code == 409

        sources = await client.get("/api/v1/sources/")
        assert sources.status_code == 200

        rejected = await client.post(
            "/api/v1/web/acquire",
            json={"url": "http://127.0.0.1/private"},
        )
        assert rejected.status_code == 403
