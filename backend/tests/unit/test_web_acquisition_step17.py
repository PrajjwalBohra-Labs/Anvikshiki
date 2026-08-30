from unittest.mock import AsyncMock, patch

import httpx
import pytest

from backend.app.application.use_cases.web_acquisition import WebAcquisitionService
from backend.app.application.use_cases.web_search import (
    WebSearchService,
    canonicalize_url,
)
from backend.app.core.config import settings
from backend.app.core.errors import AnvikshikiDomainError
from backend.app.infrastructure.storage.local_storage import LocalStorageService


def test_canonicalize_url_removes_fragment_and_default_port() -> None:
    assert canonicalize_url("HTTPS://Example.COM:443/thesis?a=2&a=1#page") == (
        "https://example.com/thesis?a=2&a=1"
    )


def test_html_metadata_extraction_is_non_executing() -> None:
    metadata = WebAcquisitionService._metadata_from_content(
        b'<html lang="sa"><head><title>Nyaya</title><meta name="author" content="Gautama">'
        b'<script>raise RuntimeError()</script></head><body><p>Pramana and inference.</p></body></html>',
        "text/html",
        "https://example.com/nyaya",
    )
    assert metadata["title"] == "Nyaya"
    assert metadata["language"] == "sa"
    assert metadata["author"] == "Gautama"


@pytest.mark.asyncio
async def test_fetch_cache_reuses_raw_response_and_metadata(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(settings, "CACHE_LOCAL_ROOT", str(tmp_path / "cache"))
    monkeypatch.setattr(settings, "STORAGE_LOCAL_ROOT", str(tmp_path / "originals"))
    monkeypatch.setattr(settings, "WEB_RESPECT_ROBOTS", False)
    storage = LocalStorageService()
    response = httpx.Response(
        200,
        headers={"content-type": "text/html; charset=utf-8", "etag": "stable"},
        content=b"<html><body><p>Raw philosophical source.</p></body></html>",
        request=httpx.Request("GET", "https://example.com/source"),
    )
    with patch.object(httpx.AsyncClient, "get", new_callable=AsyncMock, return_value=response) as mock_get:
        service = WebAcquisitionService(None, storage)
        first = await service._fetch("https://example.com/source", "https://example.com/source")
        second = await service._fetch("https://example.com/source", "https://example.com/source")
    assert first["content"] == second["content"]
    assert first["cache_hit"] is False
    assert second["cache_hit"] is True
    assert second["response_headers"]["etag"] == "stable"
    assert mock_get.await_count == 1
    assert list(storage.cached_web_dir.glob("*.json"))
    assert not list(storage.cached_web_dir.glob("*.tmp"))


@pytest.mark.asyncio
async def test_failed_fetch_does_not_create_cache_entry(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(settings, "CACHE_LOCAL_ROOT", str(tmp_path / "cache"))
    monkeypatch.setattr(settings, "WEB_RESPECT_ROBOTS", False)
    storage = LocalStorageService()
    response = httpx.Response(503, content=b"unavailable", request=httpx.Request("GET", "https://example.com"))
    with patch.object(httpx.AsyncClient, "get", new_callable=AsyncMock, return_value=response), pytest.raises(
        AnvikshikiDomainError, match="Failed to retrieve"
    ):
        await WebAcquisitionService(None, storage)._fetch("https://example.com", "https://example.com/")
    assert not list(storage.cached_web_dir.glob("*"))


@pytest.mark.asyncio
async def test_fetch_timeout_is_an_explicit_failure(monkeypatch) -> None:
    monkeypatch.setattr(settings, "WEB_RESPECT_ROBOTS", False)
    with patch.object(
        httpx.AsyncClient,
        "get",
        new_callable=AsyncMock,
        side_effect=httpx.ReadTimeout("timed out"),
    ), pytest.raises(AnvikshikiDomainError, match="Failed to retrieve"):
        await WebAcquisitionService(None, None)._fetch("https://example.com", "https://example.com/")


@pytest.mark.asyncio
async def test_robots_disallowed_is_explicit_failure(monkeypatch) -> None:
    monkeypatch.setattr(settings, "WEB_RESPECT_ROBOTS", True)
    robots = httpx.Response(
        200,
        content=b"User-agent: AnvikshikiResearchBot\nDisallow: /",
        request=httpx.Request("GET", "https://example.com/robots.txt"),
    )
    with patch.object(httpx.AsyncClient, "get", new_callable=AsyncMock, return_value=robots), pytest.raises(
        AnvikshikiDomainError, match="robots policy disallows"
    ):
        await WebAcquisitionService(None, None)._robots_allowed(
            httpx.AsyncClient(), "https://example.com/source"
        )


@pytest.mark.asyncio
async def test_search_returns_explicit_ranked_discovery_results(monkeypatch) -> None:
    html = b'''<div class="result"><a class="result__a" href="https://example.com/a#x">A</a>
    <a class="result__snippet">Snippet A</a></div>'''
    response = httpx.Response(
        200,
        headers={"content-type": "text/html"},
        content=html,
        request=httpx.Request("GET", "https://html.duckduckgo.com/html/"),
    )
    with patch.object(httpx.AsyncClient, "get", new_callable=AsyncMock, return_value=response):
        results = await WebSearchService().search("Indian epistemology", 1)
    assert results[0].canonical_url == "https://example.com/a"
    assert results[0].rank == 1
    assert results[0].snippet == "Snippet A"


@pytest.mark.asyncio
async def test_malformed_search_response_is_an_explicit_failure() -> None:
    response = httpx.Response(
        200,
        content=b"<html><body>challenge page</body></html>",
        request=httpx.Request("GET", "https://lite.duckduckgo.com/lite/"),
    )
    with patch.object(httpx.AsyncClient, "get", new_callable=AsyncMock, return_value=response), pytest.raises(
        AnvikshikiDomainError, match="no parseable results"
    ):
        await WebSearchService().search("Indian epistemology", 1)
