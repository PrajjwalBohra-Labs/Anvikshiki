import pytest
import json
from httpx import AsyncClient, ASGITransport
from backend.app.main import app
from backend.app.infrastructure.database.session import engine, Base
from backend.app.infrastructure.database.models import UserModel

@pytest.fixture
async def setup_test_env():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

@pytest.mark.asyncio
async def test_full_api_v1_e2e_execution(setup_test_env):
    from backend.app.infrastructure.database.session import AsyncSessionLocal

    async with AsyncSessionLocal() as session:
        user = UserModel(username="e2e_scholar")
        session.add(user)
        await session.commit()
        user_id = user.id

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # 1. Health check
        h_res = await client.get("/health")
        assert h_res.status_code == 200
        assert h_res.json()["status"] == "healthy"

        # 2. Create Conversation
        conv_res = await client.post("/api/v1/conversations", json={"user_id": user_id, "title": "Nyaya Epistemology"})
        assert conv_res.status_code == 200
        conv_id = conv_res.json()["conversation_id"]

        # 3. Add and Retrieve Message
        msg_res = await client.post(
            f"/api/v1/conversations/{conv_id}/messages",
            json={"role": "user", "content": "How is perception validated in Nyaya?"}
        )
        assert msg_res.status_code == 200
        assert msg_res.json()["content"] == "How is perception validated in Nyaya?"

        # 4. Execute Socratic Dialogue Turn
        diag_res = await client.post(
            "/api/v1/dialogue/turn",
            json={"user_utterance": "Perception is self-evident.", "dialogue_mode": "socratic"}
        )
        assert diag_res.status_code == 200
        assert "?" in diag_res.json()["response_text"]

        # 5. Execute LangGraph Research Run
        res_run = await client.post(
            "/api/v1/research/run",
            json={"user_id": user_id, "query": "Criteria of valid cognition", "domain": "Epistemology"}
        )
        assert res_run.status_code == 200
        assert res_run.json()["status"] in ["APPROVED", "BLOCKED_OR_DOWNGRADED", "PENDING"]
        assert len(res_run.json()["safe_events"]) > 0

        # 6. Stream Research SSE Events
        sse_res = await client.post(
            "/api/v1/research/run/stream",
            json={"user_id": user_id, "query": "Criteria of valid cognition"}
        )
        assert sse_res.status_code == 200
        assert "text/event-stream" in sse_res.headers["content-type"]
        assert "data:" in sse_res.text

        # 7. Record and Update Epistemic Position
        pos_res = await client.post(
            "/api/v1/epistemic/positions",
            json={
                "user_id": user_id,
                "claim_statement": "Perception requires non-erroneous cognition.",
                "position": "tentative",
                "confidence": 0.9,
                "status": "tentative"
            }
        )
        assert pos_res.status_code == 200
        pos_id = pos_res.json()["position_id"]

        patch_res = await client.patch(
            f"/api/v1/epistemic/positions/{pos_id}/status",
            json={"new_status": "accepted", "change_reason": "Verified against Nyaya Sutra passage 1.1.4"}
        )
        assert patch_res.status_code == 200
        assert patch_res.json()["status"] == "accepted"