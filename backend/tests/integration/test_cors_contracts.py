import pytest
from httpx import ASGITransport, AsyncClient

from backend.app.infrastructure.database.session import Base, engine
from backend.app.main import app


@pytest.fixture
async def clean_database():
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.drop_all)
        await connection.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.drop_all)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "origin",
    ["http://localhost:5173", "http://127.0.0.1:5173", "http://192.168.1.38:5173"],
)
async def test_users_preflight_allows_local_frontend_origins(origin: str):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.options(
            "/api/v1/users",
            headers={
                "Origin": origin,
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "content-type,authorization",
            },
        )

    assert 200 <= response.status_code < 300
    assert response.headers["access-control-allow-origin"] == origin
    assert response.headers["access-control-allow-credentials"] == "true"
    assert "POST" in response.headers["access-control-allow-methods"]
    allowed_headers = response.headers["access-control-allow-headers"].lower()
    assert "content-type" in allowed_headers
    assert "authorization" in allowed_headers


@pytest.mark.asyncio
async def test_users_registration_accepts_cors_origin(clean_database):
    username = "cors_debug_test_20260828"
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/v1/users",
            headers={"Origin": "http://127.0.0.1:5173", "Content-Type": "application/json"},
            json={"username": username},
        )

    assert response.status_code == 201
    assert response.json()["username"] == username
    assert response.json()["access_token"]
    assert response.headers["access-control-allow-origin"] == "http://127.0.0.1:5173"
