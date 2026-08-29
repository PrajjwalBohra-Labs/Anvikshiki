import pytest
from httpx import ASGITransport, AsyncClient

from backend.app.application.use_cases.user_service import UserService
from backend.app.core.config import settings
from backend.app.domain.models.enums import SourceType
from backend.app.infrastructure.database.models import DocumentModel, SourceModel
from backend.app.infrastructure.database.session import AsyncSessionLocal, Base, engine
from backend.app.infrastructure.storage.local_storage import LocalStorageService
from backend.app.main import app


@pytest.fixture
async def storage_api_environment(tmp_path, monkeypatch):
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.drop_all)
        await connection.run_sync(Base.metadata.create_all)

    monkeypatch.setattr(settings, "STORAGE_LOCAL_ROOT", str(tmp_path / "originals"))
    previous_auth_mode = settings.AUTH_MODE
    settings.AUTH_MODE = "required"
    yield
    settings.AUTH_MODE = previous_auth_mode

    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.drop_all)


@pytest.mark.asyncio
async def test_document_file_requires_authentication_and_allows_authenticated_retrieval(
    storage_api_environment,
):
    content = b"A preserved local original."
    async with AsyncSessionLocal() as session:
        source = SourceModel(title="Storage test source", source_type=SourceType.PRIMARY)
        session.add(source)
        await session.flush()

        metadata = await LocalStorageService().store_original(content, "original.txt")
        document = DocumentModel(
            source_id=source.id,
            checksum_sha256=metadata.checksum_sha256,
            mime_type=metadata.mime_type,
            original_filename=metadata.original_filename,
            storage_path=metadata.storage_path,
            size_bytes=metadata.size_bytes,
            total_pages=1,
        )
        session.add(document)
        user, token = await UserService(session).create_user("storage_api_user")
        await session.commit()
        document_id = document.id

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        unauthorized = await client.get(f"/api/v1/documents/{document_id}/file")
        assert unauthorized.status_code == 401

        authorized = await client.get(
            f"/api/v1/documents/{document_id}/file",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert authorized.status_code == 200
        assert authorized.content == content
        assert authorized.headers["content-type"].startswith("text/plain")
        assert user.id
