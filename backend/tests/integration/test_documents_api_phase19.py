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
async def test_source_and_document_upload_api():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # 1. Create a Source
        source_payload = {
            "title": "Brahma Sutras",
            "author": "Badarayana",
            "source_type": "PRIMARY"
        }
        res_source = await ac.post(f"{settings.API_V1_STR}/sources/", json=source_payload)
        assert res_source.status_code == 201
        source_data = res_source.json()
        source_id = source_data["id"]
        
        # 2. Upload a text document linked to the source
        file_content = b"Chapter 1: Atha ato brahma-jijnasa.\n\nNow follows the inquiry into Brahman."
        files = {"file": ("brahma_sutras.txt", file_content, "text/plain")}
        data = {"source_id": source_id}
        
        res_upload = await ac.post(f"{settings.API_V1_STR}/documents/upload", data=data, files=files)
        assert res_upload.status_code == 201
        upload_data = res_upload.json()
        doc_id = upload_data["document_id"]
        assert upload_data["passages_count"] == 2
        
        # 3. Fetch passages for the document
        res_passages = await ac.get(f"{settings.API_V1_STR}/documents/{doc_id}/passages")
        assert res_passages.status_code == 200
        passages = res_passages.json()
        assert len(passages) == 2
        assert "brahma-jijnasa" in passages[0]["content"]