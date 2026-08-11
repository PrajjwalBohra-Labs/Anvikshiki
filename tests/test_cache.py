from app.infrastructure.cache import CacheStore


def test_set_and_get_round_trip():
    cache = CacheStore()
    cache.set("key", "value")
    assert cache.get("key") == "value"


def test_get_missing_key_returns_none():
    cache = CacheStore()
    assert cache.get("missing") is None


def test_invalidate_removes_a_key():
    cache = CacheStore()
    cache.set("key", "value")
    cache.invalidate("key")
    assert cache.get("key") is None


def test_clear_removes_all_keys():
    cache = CacheStore()
    cache.set("a", 1)
    cache.set("b", 2)
    cache.clear()
    assert len(cache) == 0


def test_expired_ttl_entry_returns_none():
    cache = CacheStore()
    cache.set("key", "value", ttl_seconds=-1)  # already expired
    assert cache.get("key") is None


def test_entry_without_ttl_does_not_expire():
    cache = CacheStore()
    cache.set("key", "value")  # no ttl
    assert cache.get("key") == "value"
