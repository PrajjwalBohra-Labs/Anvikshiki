from types import SimpleNamespace

import pytest
from structlog.testing import capture_logs

from backend.app.api.dependencies import AuthenticatedPrincipal
from backend.app.api.v1.endpoints.sources import (
    SOURCE_LIST_CACHE_KEY,
    SourceResponse,
    list_sources,
    source_list_cache,
)
from backend.app.infrastructure.cache.in_memory import InMemoryTTLCache


def source_record(identifier: str = "source-1") -> SimpleNamespace:
    return SimpleNamespace(
        id=identifier,
        title="A source",
        author=None,
        historical_era=None,
        original_language=None,
        source_type="UNVERIFIED",
        reference_url=None,
    )


class FakeScalarResult:
    def __init__(self, values):
        self.values = values

    def scalars(self):
        return self

    def all(self):
        return self.values


class FakeSession:
    def __init__(self, values):
        self.values = values
        self.calls = 0

    async def execute(self, _statement):
        self.calls += 1
        return FakeScalarResult(self.values)


@pytest.fixture(autouse=True)
def clear_source_cache():
    source_list_cache.clear()
    yield
    source_list_cache.clear()


def test_ttl_cache_miss_hit_expiry_and_invalidation(monkeypatch):
    clock = [100.0]
    monkeypatch.setattr("backend.app.infrastructure.cache.in_memory.monotonic", lambda: clock[0])
    cache = InMemoryTTLCache(ttl_seconds=5)
    assert cache.get("safe-key") is None
    cache.set("safe-key", [{"id": "one"}])
    assert cache.get("safe-key") == [{"id": "one"}]
    clock[0] = 106.0
    assert cache.get("safe-key") is None
    cache.set("safe-key", [{"id": "one"}])
    cache.invalidate("safe-key")
    assert cache.get("safe-key") is None


@pytest.mark.asyncio
async def test_authenticated_source_reads_use_authoritative_data_then_cache_hit():
    session = FakeSession([source_record()])
    principal = AuthenticatedPrincipal(user_id="user-a", username="a")
    first = await list_sources(session, principal)
    second = await list_sources(FakeSession([]), principal)
    assert first == [SourceResponse.model_validate(source_record()).model_dump()]
    assert second == first
    assert session.calls == 1


@pytest.mark.asyncio
async def test_cache_failure_fails_open_without_caching_an_error(monkeypatch):
    session = FakeSession([source_record("source-fallback")])
    principal = AuthenticatedPrincipal(user_id="user-a", username="a")

    def broken_get(_key):
        raise RuntimeError("cache unavailable")

    monkeypatch.setattr(source_list_cache, "get", broken_get)
    with capture_logs() as events:
        result = await list_sources(session, principal)
    assert result[0]["id"] == "source-fallback"
    assert session.calls == 1
    assert any(event.get("event") == "cache_fallback" for event in events)
    assert "cache unavailable" not in str(events)


@pytest.mark.asyncio
async def test_cache_population_failure_returns_authoritative_data(monkeypatch):
    session = FakeSession([source_record("source-set-fallback")])
    principal = AuthenticatedPrincipal(user_id="user-a", username="a")

    def broken_set(_key, _value):
        raise RuntimeError("cache write unavailable")

    monkeypatch.setattr(source_list_cache, "set", broken_set)
    with capture_logs() as events:
        result = await list_sources(session, principal)
    assert result[0]["id"] == "source-set-fallback"
    assert session.calls == 1
    assert any(event.get("event") == "cache_fallback" for event in events)
    assert "cache write unavailable" not in str(events)
    assert source_list_cache.get(SOURCE_LIST_CACHE_KEY) is None


@pytest.mark.asyncio
async def test_authoritative_read_failure_does_not_create_cache_entry():
    class BrokenSession:
        async def execute(self, _statement):
            raise RuntimeError("database unavailable")

    principal = AuthenticatedPrincipal(user_id="user-a", username="a")
    with pytest.raises(RuntimeError):
        await list_sources(BrokenSession(), principal)
    assert source_list_cache.get(SOURCE_LIST_CACHE_KEY) is None
