import pytest
from httpx import ASGITransport, AsyncClient

from backend.app.core.config import settings
from backend.app.main import app


@pytest.mark.asyncio
async def test_private_retrieval_and_reasoning_endpoints_require_authentication():
    previous_auth_mode = settings.AUTH_MODE
    settings.AUTH_MODE = "required"
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            search = await client.get("/api/v1/search/", params={"query": "knowledge"})
            reasoning = await client.post(
                "/api/v1/reasoning/synthesize", json={"query": "knowledge"}
            )
            dialogue = await client.post(
                "/api/v1/dialogue/turn",
                json={"user_utterance": "What is knowledge?", "dialogue_mode": "socratic"},
            )
        assert [response.status_code for response in (search, reasoning, dialogue)] == [401, 401, 401]
    finally:
        settings.AUTH_MODE = previous_auth_mode
