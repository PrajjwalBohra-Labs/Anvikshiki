"""
Web Search Adapter (post-Step-16 amendment: Web-Augmented Knowledge).
Same seam pattern as the LLM Adapter (Step 3): an ABC, one real
implementation (Tavily), and a no-op stub used whenever web search
isn't available -- so "disabled" is a real code path, not just a
config flag nobody enforces.

Uses Tavily's basic /search endpoint only (1 credit/call) -- NOT the
dedicated /research endpoint (4-250 credits/call), which would burn
through the free tier's 1,000 monthly credits in a handful of calls.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

import httpx

from app.config import Settings, get_settings
from app.infrastructure.observability import record_event

TAVILY_SEARCH_URL = "https://api.tavily.com/search"


@dataclass
class WebSearchResult:
    title: str
    url: str
    content: str
    score: float


class WebSearchAdapter(ABC):
    @abstractmethod
    def search(self, query: str, max_results: int = 3) -> list[WebSearchResult]: ...


class TavilyAdapter(WebSearchAdapter):
    """The one real implementation. Basic search depth only."""

    def __init__(self, settings: Settings | None = None, client: httpx.Client | None = None):
        self._settings = settings or get_settings()
        self._client = client or httpx.Client(timeout=20.0)

    def search(self, query: str, max_results: int = 3) -> list[WebSearchResult]:
        # Graceful degradation (§4/§29): web search is opt-in and
        # additive to local retrieval -- a Tavily failure must never
        # be able to break a request that would have worked fine
        # with web search off. Degrade to no web results, not a crash.
        try:
            response = self._client.post(
                TAVILY_SEARCH_URL,
                json={
                    "api_key": self._settings.tavily_api_key,
                    "query": query,
                    "search_depth": "basic",
                    "max_results": max_results,
                },
            )
            response.raise_for_status()
            data = response.json()
        except (httpx.ConnectError, httpx.TimeoutException, httpx.HTTPStatusError) as exc:
            record_event("web_search", "failure", error=str(exc), error_type=type(exc).__name__)
            return []

        return [
            WebSearchResult(
                title=item.get("title", "Untitled"),
                url=item.get("url", ""),
                content=item.get("content", ""),
                score=item.get("score", 0.0),
            )
            for item in data.get("results", [])
        ]


class NoOpWebSearchAdapter(WebSearchAdapter):
    """Used whenever web search is disabled or unconfigured. Returns
    no results rather than erroring -- the system degrades to
    local-only, which is the documented default."""

    def search(self, query: str, max_results: int = 3) -> list[WebSearchResult]:
        return []


def get_web_search_adapter(settings: Settings | None = None) -> WebSearchAdapter:
    settings = settings or get_settings()
    if settings.web_search_enabled and settings.tavily_api_key:
        return TavilyAdapter(settings)
    return NoOpWebSearchAdapter()

