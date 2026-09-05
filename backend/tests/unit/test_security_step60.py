import json

import pytest
from httpx import ASGITransport, AsyncClient
from starlette.requests import Request
from structlog.testing import capture_logs

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
    assert first.headers["x-request-id"] != second.headers["x-request-id"]
    assert first.headers["x-content-type-options"] == "nosniff"
    assert first.headers["x-frame-options"] == "DENY"
    assert first.headers["referrer-policy"] == "no-referrer"
    assert first.headers["cache-control"] == "no-store"


@pytest.mark.asyncio
async def test_health_check_does_not_expose_database_exception(monkeypatch):
    class BrokenSession:
        async def __aenter__(self):
            raise RuntimeError("private database path")

        async def __aexit__(self, *_args):
            return False

    monkeypatch.setattr("backend.app.main.AsyncSessionLocal", lambda: BrokenSession())
    result = await health_check()
    assert result["database"] == "unavailable"
    assert "private database path" not in str(result)


@pytest.mark.asyncio
async def test_request_logs_are_structured_without_sensitive_values():
    with capture_logs() as events:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/health", headers={"Authorization": "Bearer secret-token"})
    event = next(item for item in events if item.get("event") == "http_request")
    assert response.status_code == 200
    assert event["request_id"] == response.headers["x-request-id"]
    assert "secret-token" not in str(event)


@pytest.mark.asyncio
async def test_internal_error_responses_are_sanitized():
    response = await global_exception_handler(request_for(), RuntimeError("secret-token / private/path"))
    assert json.loads(response.body) == {"error": "An internal server error occurred.", "type": "internal_error"}
    response = await domain_error_handler(request_for(), AnvikshikiDomainError("private path", status_code=500))
    assert json.loads(response.body)["error"] == "An internal server error occurred."
