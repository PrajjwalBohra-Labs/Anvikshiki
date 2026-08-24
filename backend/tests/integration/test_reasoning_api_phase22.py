import pytest
from httpx import AsyncClient, ASGITransport
from backend.app.main import app
from backend.app.core.config import settings
from backend.app.infrastructure.database.session import engine, Base

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
async def test_reasoning_synthesis_api():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # 1. Create Source
        source_payload = {
            "title": "Bhashapariccheda",
            "source_type": "PRIMARY"
        }
        res_source = await ac.post(f"{settings.API_V1_STR}/sources/", json=source_payload)
        source_id = res_source.json()["id"]
        
        # 2. Upload Document
        file_content = b"Perception is produced by the contact of senses with objects."
        files = {"file": ("nyaya_text.txt", file_content, "text/plain")}
        data = {"source_id": source_id}
        await ac.post(f"{settings.API_V1_STR}/documents/upload", data=data, files=files)
        
        # 3. Call Reasoning Synthesis Endpoint
        payload = {
            "query": "sense contact perception",
            "source_type": "PRIMARY"
        }
        response = await ac.post(f"{settings.API_V1_STR}/reasoning/synthesize", json=payload)
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["conclusion"] is not None
        assert len(data["premises"]) == 1
        assert len(data["evidence_links"]) == 1
        assert data["pramana_type"] == "anumana"
        assert data["overall_status"] == "supported"