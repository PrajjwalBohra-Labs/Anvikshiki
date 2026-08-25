import pytest
from unittest.mock import patch, MagicMock
from sqlalchemy.ext.asyncio import AsyncSession
from backend.app.infrastructure.database.session import engine, Base
from backend.app.infrastructure.storage.local_storage import LocalStorageService
from backend.app.application.use_cases.web_acquisition import WebAcquisitionService
from backend.app.domain.models.enums import SourceType

@pytest.fixture
async def setup_test_env(tmp_path, monkeypatch):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    
    from backend.app.core.config import settings
    monkeypatch.setattr(settings, "STORAGE_LOCAL_ROOT", str(tmp_path / "originals"))
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

@pytest.mark.asyncio
@patch("httpx.AsyncClient.get")
async def test_web_acquisition_lifecycle(mock_get, setup_test_env):
    # Mock HTTP response with synchronous raise_for_status
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.text = """
    <html>
        <head><title>Stanford Encyclopedia of Philosophy: Epistemology</title></head>
        <body>
            <nav>Menu items to ignore</nav>
            <p>Epistemology is the study of knowledge and justified true belief.</p>
            <p>Classical Indian epistemology focuses heavily on valid means of knowledge known as pramanas.</p>
        </body>
    </html>
    """
    mock_response.headers = {"content-type": "text/html; charset=utf-8"}
    mock_response.content = mock_response.text.encode("utf-8")
    mock_response.raise_for_status = MagicMock()
    mock_get.return_value = mock_response

    from backend.app.infrastructure.database.session import AsyncSessionLocal
    storage = LocalStorageService()

    async with AsyncSessionLocal() as session:
        service = WebAcquisitionService(session, storage)
        
        test_url = "https://plato.stanford.edu/entries/epistemology/"
        source, doc, passages = await service.acquire_url(test_url)
        
        assert source.title == "Stanford Encyclopedia of Philosophy: Epistemology"
        assert source.source_type == SourceType.DISCOVERY_ONLY
        assert source.reference_url == test_url
        assert doc.mime_type == "text/html"
        assert len(passages) == 2
        assert "justified true belief" in passages[0].content
        assert "pramanas" in passages[1].content
