import pytest
from httpx import ASGITransport, AsyncClient

from backend.app.application.use_cases.user_service import UserService
from backend.app.core.config import settings
from backend.app.infrastructure.database.models import Base
from backend.app.infrastructure.database.session import AsyncSessionLocal, engine
from backend.app.main import app


@pytest.fixture
async def notebook_database():
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.drop_all)
        await connection.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.drop_all)


@pytest.mark.asyncio
async def test_notebook_crud_persists_and_isolates_authenticated_users(notebook_database):
    previous_auth_mode = settings.AUTH_MODE
    settings.AUTH_MODE = "required"
    try:
        async with AsyncSessionLocal() as session:
            owner, owner_token = await UserService(session).create_user("notebook_owner")
            other, other_token = await UserService(session).create_user("notebook_other")

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            unauthenticated = await client.get("/api/v1/notebooks")
            assert unauthenticated.status_code == 401

            created = await client.post(
                "/api/v1/notebooks",
                headers={"Authorization": f"Bearer {owner_token}"},
                json={"title": "First notes", "content": "A durable observation."},
            )
            assert created.status_code == 201
            notebook = created.json()
            assert set(notebook) == {"notebook_id", "title", "content", "created_at", "updated_at"}

            listed = await client.get("/api/v1/notebooks", headers={"Authorization": f"Bearer {owner_token}"})
            assert listed.status_code == 200
            assert listed.json()[0]["notebook_id"] == notebook["notebook_id"]

            fetched = await client.get(
                f"/api/v1/notebooks/{notebook['notebook_id']}",
                headers={"Authorization": f"Bearer {owner_token}"},
            )
            assert fetched.status_code == 200
            assert fetched.json()["content"] == "A durable observation."

            updated = await client.patch(
                f"/api/v1/notebooks/{notebook['notebook_id']}",
                headers={"Authorization": f"Bearer {owner_token}"},
                json={"content": "An edited observation."},
            )
            assert updated.status_code == 200
            assert updated.json()["content"] == "An edited observation."

            foreign_read = await client.get(
                f"/api/v1/notebooks/{notebook['notebook_id']}",
                headers={"Authorization": f"Bearer {other_token}"},
            )
            assert foreign_read.status_code == 404

            foreign_delete = await client.delete(
                f"/api/v1/notebooks/{notebook['notebook_id']}",
                headers={"Authorization": f"Bearer {other_token}"},
            )
            assert foreign_delete.status_code == 404

            invalid = await client.post(
                "/api/v1/notebooks",
                headers={"Authorization": f"Bearer {owner_token}"},
                json={"title": "invalid", "content": "", "user_id": owner.id},
            )
            assert invalid.status_code == 422

            blank_title = await client.post(
                "/api/v1/notebooks",
                headers={"Authorization": f"Bearer {owner_token}"},
                json={"title": "   ", "content": "not a valid title"},
            )
            assert blank_title.status_code == 422

            empty_patch = await client.patch(
                f"/api/v1/notebooks/{notebook['notebook_id']}",
                headers={"Authorization": f"Bearer {owner_token}"},
                json={},
            )
            assert empty_patch.status_code == 422

            deleted = await client.delete(
                f"/api/v1/notebooks/{notebook['notebook_id']}",
                headers={"Authorization": f"Bearer {owner_token}"},
            )
            assert deleted.status_code == 204
            assert (await client.get(
                f"/api/v1/notebooks/{notebook['notebook_id']}",
                headers={"Authorization": f"Bearer {owner_token}"},
            )).status_code == 404
    finally:
        settings.AUTH_MODE = previous_auth_mode
