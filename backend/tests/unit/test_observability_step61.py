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


def request_for() -> Request:
    return Request({"type": "http", "method": "GET", "path": "/test", "headers": [], "query_string": b""})


@pytest.mark.asyncio
async def test_http_observability_has_safe_correlation_fields():
    with capture_logs() as events:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/health", headers={"Authorization": "Bearer secret-token"})
    request_event = next(event for event in events if event.get("event") == "http_request")
    assert response.status_code == 200
    assert response.headers["x-request-id"] == request_event["request_id"]
    assert request_event["method"] == "GET"
    assert request_event["status_code"] == 200
    assert isinstance(request_event["duration_ms"], float)
    assert "secret-token" not in str(events)


@pytest.mark.asyncio
async def test_valid_request_id_is_preserved_and_invalid_id_is_replaced():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        preserved = await client.get("/health", headers={"X-Request-ID": "12345678-1234-4234-8234-123456789abc"})
        replaced = await client.get("/health", headers={"X-Request-ID": "not-a-uuid"})
    assert preserved.headers["x-request-id"] == "12345678123442348234123456789abc"
    assert replaced.headers["x-request-id"] != "not-a-uuid"


@pytest.mark.asyncio
async def test_health_failure_is_observable_but_sanitized(monkeypatch):
    class BrokenSession:
        async def __aenter__(self):
            raise RuntimeError("database secret path")

        async def __aexit__(self, *_args):
            return False

    monkeypatch.setattr("backend.app.main.AsyncSessionLocal", lambda: BrokenSession())
    with capture_logs() as events:
        result = await health_check()
    assert result["database"] == "unavailable"
    assert "database secret path" not in str(result)
    assert any(event.get("event") == "health_check_failed" for event in events)
    assert "database secret path" not in str(events)


@pytest.mark.asyncio
async def test_error_handlers_keep_internal_details_out_of_responses_and_logs():
    with capture_logs() as events:
        response = await global_exception_handler(request_for(), RuntimeError("private token / path"))
        domain_response = await domain_error_handler(
            request_for(), AnvikshikiDomainError("private database path", status_code=500)
        )
    assert json.loads(response.body)["error"] == "An internal server error occurred."
    assert json.loads(domain_response.body)["error"] == "An internal server error occurred."
    assert "private token" not in str(events)
    assert "private database path" not in str(events)
