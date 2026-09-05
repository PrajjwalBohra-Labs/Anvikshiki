from types import SimpleNamespace

import pytest

from backend.app.application.use_cases import web_research
from backend.app.application.use_cases.web_search import WebSearchResult
from backend.app.core.errors import AnvikshikiDomainError


class _SessionContext:
    async def __aenter__(self):
        return object()

    async def __aexit__(self, _exc_type, _exc_value, _traceback):
        return False


@pytest.mark.asyncio
async def test_web_research_acquires_discoveries_before_returning_evidence(monkeypatch):
    candidate = WebSearchResult(
        title="A public source",
        url="https://example.com/source",
        canonical_url="https://example.com/source",
        snippet="A source description.",
        rank=1,
        domain="example.com",
    )

    async def search(_self, _query, _limit):
        return [candidate]

    async def acquire(self, **_kwargs):
        return (
            SimpleNamespace(id="source-1"),
            SimpleNamespace(id="document-1"),
            [SimpleNamespace(id="passage-1")],
        )

    monkeypatch.setattr(web_research.WebSearchService, "search", search)
    monkeypatch.setattr(web_research.WebAcquisitionService, "acquire_url", acquire)

    result = await web_research.WebResearchService(
        lambda: _SessionContext(), storage_factory=lambda: object()
    ).discover_and_acquire("a question", "user-1")

    assert result["status"] == "acquired"
    assert result["discoveries"][0]["canonical_url"] == candidate.canonical_url
    assert result["acquisitions"] == [
        {
            "status": "acquired",
            "url": candidate.canonical_url,
            "source_id": "source-1",
            "document_id": "document-1",
            "passages_count": 1,
        }
    ]


@pytest.mark.asyncio
async def test_web_research_reports_search_unavailability_without_fabricating_evidence(monkeypatch):
    async def search(_self, _query, _limit):
        raise AnvikshikiDomainError("Web search is temporarily unavailable.", status_code=502)

    monkeypatch.setattr(web_research.WebSearchService, "search", search)

    result = await web_research.WebResearchService(
        lambda: _SessionContext(), storage_factory=lambda: object()
    ).discover_and_acquire("a question", "user-1")

    assert result["status"] == "unavailable"
    assert result["discoveries"] == []
    assert result["acquisitions"] == []
