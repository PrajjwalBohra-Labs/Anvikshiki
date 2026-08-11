import httpx
import pytest

from app.config import Settings
from app.infrastructure.web_search_adapter import (
    NoOpWebSearchAdapter,
    TavilyAdapter,
    get_web_search_adapter,
)


def test_noop_adapter_returns_no_results():
    adapter = NoOpWebSearchAdapter()
    assert adapter.search("anything") == []


def test_get_web_search_adapter_returns_noop_when_disabled():
    settings = Settings(web_search_enabled=False, tavily_api_key="some-key")
    assert isinstance(get_web_search_adapter(settings), NoOpWebSearchAdapter)


def test_get_web_search_adapter_returns_noop_when_no_key():
    settings = Settings(web_search_enabled=True, tavily_api_key="")
    assert isinstance(get_web_search_adapter(settings), NoOpWebSearchAdapter)


def test_get_web_search_adapter_returns_tavily_when_configured():
    settings = Settings(web_search_enabled=True, tavily_api_key="real-key")
    assert isinstance(get_web_search_adapter(settings), TavilyAdapter)


def test_tavily_adapter_sends_basic_search_depth_and_parses_results():
    def handler(request: httpx.Request) -> httpx.Response:
        import json
        body = json.loads(request.content)
        assert body["search_depth"] == "basic"
        assert body["api_key"] == "real-key"
        return httpx.Response(
            200,
            json={"results": [{"title": "A Real Paper", "url": "https://example.com", "content": "text", "score": 0.9}]},
        )

    client = httpx.Client(transport=httpx.MockTransport(handler))
    settings = Settings(web_search_enabled=True, tavily_api_key="real-key")
    adapter = TavilyAdapter(settings=settings, client=client)

    results = adapter.search("test query")
    assert len(results) == 1
    assert results[0].title == "A Real Paper"
import httpx
import pytest

from app.config import Settings
from app.infrastructure.web_search_adapter import TavilyAdapter


def test_tavily_adapter_degrades_to_empty_list_on_connection_failure():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("simulated network failure", request=request)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    settings = Settings(web_search_enabled=True, tavily_api_key="real-key")
    adapter = TavilyAdapter(settings=settings, client=client)

    results = adapter.search("anything")
    assert results == []  # degraded, did not raise


def test_tavily_adapter_degrades_to_empty_list_on_http_error():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={"error": "server error"})

    client = httpx.Client(transport=httpx.MockTransport(handler))
    settings = Settings(web_search_enabled=True, tavily_api_key="real-key")
    adapter = TavilyAdapter(settings=settings, client=client)

    results = adapter.search("anything")
    assert results == []
import httpx
import pytest

from app.config import Settings
from app.infrastructure.web_search_adapter import TavilyAdapter


def test_tavily_adapter_degrades_to_empty_list_on_connection_failure():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("simulated network failure", request=request)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    settings = Settings(web_search_enabled=True, tavily_api_key="real-key")
    adapter = TavilyAdapter(settings=settings, client=client)

    results = adapter.search("anything")
    assert results == []  # degraded, did not raise


def test_tavily_adapter_degrades_to_empty_list_on_http_error():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={"error": "server error"})

    client = httpx.Client(transport=httpx.MockTransport(handler))
    settings = Settings(web_search_enabled=True, tavily_api_key="real-key")
    adapter = TavilyAdapter(settings=settings, client=client)

    results = adapter.search("anything")
    assert results == []
