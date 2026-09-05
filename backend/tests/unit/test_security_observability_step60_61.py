import json

import pytest
from httpx import ASGITransport, AsyncClient
from starlette.requests import Request
from structlog.testing import capture_logs

from backend.app.core.config import settings
from backend.app.core.errors import (
    AnvikshikiDomainError,
    domain_error_handler,
    global_exception_handler,
)
from backend.app.main import app, health_check


def request_for(path: str = "/test") -> Request:
    return Request({"type": "http", "method": "GET", "path": path, "headers": [], "query_string": b""})


@pytest.mark.asyncio
async def test_security_headers_request_id_and_private_cache_policy():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        first = await client.get("/health")
        second = await client.get("/health")

    assert first.status_code == 200
    assert first.headers["x-request-id"]
    assert first.headers["x-request-id"] != second.headers["x-request-id"]
    assert first.headers["x-content-type-options"] == "nosniff"
    assert first.headers["x-frame-options"] == "DENY"
    assert first.headers["referrer-policy"] == "no-referrer"
    assert first.headers["permissions-policy"] == "camera=(), microphone=(), geolocation=()"
    assert first.headers["cache-control"] == "no-store"


@pytest.mark.asyncio
async def test_health_check_does_not_expose_database_exception(monkeypatch):
    class BrokenSession:
        async def __aenter__(self):
            raise RuntimeError("secret database path")

        async def __aexit__(self, exc_type, exc_value, traceback):
            return False

    monkeypatch.setattr("backend.app.main.AsyncSessionLocal", lambda: BrokenSession())

    result = await health_check()

    assert result["status"] == "degraded"
    assert result["database"] == "unavailable"
    assert "secret database path" not in str(result)


@pytest.mark.asyncio
async def test_request_observability_emits_safe_structured_event():
    with capture_logs() as events:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/health")

    request_events = [event for event in events if event.get("event") == "http_request"]
    assert response.status_code == 200
    assert request_events
    assert request_events[-1]["status_code"] == 200
    assert request_events[-1]["method"] == "GET"
    assert request_events[-1]["request_id"] == response.headers["x-request-id"]
    assert all("authorization" not in str(event).lower() for event in request_events)


@pytest.mark.asyncio
async def test_unauthenticated_auth_boundary_remains_rejected(monkeypatch):
    monkeypatch.setattr(settings, "AUTH_MODE", "required")
    async with AsyncClient(transport=ASGITransport(app), base_url="http://test") as client:
        response = await client.get("/api/v1/auth/me")

    assert response.status_code == 401
    assert "Bearer authentication is required." in response.json()["detail"]
    assert "authorization" not in response.text.lower()


@pytest.mark.asyncio
async def test_internal_errors_are_sanitized():
    response = await global_exception_handler(request_for(), RuntimeError("secret-token / private/path"))
    body = json.loads(response.body)
    assert response.status_code == 500
    assert body == {"error": "An internal server error occurred.", "type": "internal_error"}
    assert "secret-token" not in response.body.decode("utf-8")


@pytest.mark.asyncio
async def test_server_domain_errors_are_sanitized():
    response = await domain_error_handler(request_for(), AnvikshikiDomainError("/private/path", status_code=500))
    body = json.loads(response.body)
    assert response.status_code == 500
    assert body["error"] == "An internal server error occurred."
