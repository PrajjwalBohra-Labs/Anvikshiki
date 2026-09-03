import pytest
from httpx import ASGITransport, AsyncClient

from backend.app.core.config import settings
from backend.app.infrastructure.database.session import Base, engine
from backend.app.main import app


@pytest.fixture(autouse=True)
async def setup_test_db(tmp_path, monkeypatch):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    
    monkeypatch.setattr(settings, "STORAGE_LOCAL_ROOT", str(tmp_path / "originals"))
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

@pytest.mark.asyncio
async def test_chat_api_lifecycle():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # 1. Create a User via direct model insertion or setup
        from backend.app.domain.models.enums import SourceType
        from backend.app.infrastructure.database.models import (
            DocumentModel,
            PassageModel,
            SourceModel,
            UserModel,
        )
        from backend.app.infrastructure.database.session import AsyncSessionLocal
        
        async with AsyncSessionLocal() as session:
            user = UserModel(id="user_test_123", username="api_scholar")
            source = SourceModel(title="Mandukya Upanishad", author="Gaudapada", source_type=SourceType.PRIMARY)
            session.add_all([user, source])
            await session.flush()
            
            doc = DocumentModel(source_id=source.id, checksum_sha256="api_chat_hash", mime_type="text/plain")
            session.add(doc)
            await session.flush()
            
            passage = PassageModel(
                document_id=doc.id, 
                page_number=5,
                content="Turiya is the fourth state, beyond waking, dreaming, and deep sleep."
            )
            session.add(passage)
            await session.commit()

        # 2. Post a chat message to the API endpoint
        chat_payload = {
            "user_id": "user_test_123",
            "conversation_id": None,
            "message": "Explain the fourth state Turiya."
        }
        response = await ac.post(f"{settings.API_V1_STR}/chat/", json=chat_payload)
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["conversation_id"] is not None
        assert "Turiya" in data["reply"]
        assert len(data["citations"]) == 1
        assert "Mandukya Upanishad" in data["citations"][0]
        assert data["argument_summary"]["pramana"] == "anumana"
        assert data["argument_summary"]["status"] == "supported"
        
        # 3. Send a follow-up message in the same conversation
        followup_payload = {
            "user_id": "user_test_123",
            "conversation_id": data["conversation_id"],
            "message": "What states precede it?"
        }
        res_followup = await ac.post(f"{settings.API_V1_STR}/chat/", json=followup_payload)
        assert res_followup.status_code == 200
        assert res_followup.json()["conversation_id"] == data["conversation_id"]