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
async def test_search_and_citation_api():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # 1. Create a Source
        source_payload = {
            "title": "Nyaya Sutras",
            "author": "Gotama",
            "source_type": "PRIMARY"
        }
        res_source = await ac.post(f"{settings.API_V1_STR}/sources/", json=source_payload)
        source_id = res_source.json()["id"]
        
        # 2. Upload Document
        file_content = b"Perception is valid knowledge when it is non-erroneous and definite."
        files = {"file": ("nyaya.txt", file_content, "text/plain")}
        data = {"source_id": source_id}
        await ac.post(f"{settings.API_V1_STR}/documents/upload", data=data, files=files)
        
        # 3. Execute Search via API
        res_search = await ac.get(f"{settings.API_V1_STR}/search/?query=non-erroneous")
        assert res_search.status_code == 200
        search_data = res_search.json()
        
        assert search_data["total_results"] == 1
        item = search_data["results"][0]
        assert "Nyaya Sutras" in item["source_title"]
        assert "non-erroneous" in item["content"]
        assert item["citation_string"] == "Nyaya Sutras, by Gotama, p. 1"