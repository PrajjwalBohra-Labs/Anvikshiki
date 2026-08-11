"""
Ensures every test runs against a fresh, isolated SQLite/file store
instead of the real dev database. Without this, test fixtures (which
insert short fake embedding vectors) and real ingestion (which
inserts real 768-dim nomic-embed-text vectors) end up in the same
files on disk, and any query mixing them blows up on dimension
mismatch. autouse=True means every test gets this automatically.
"""

import pytest

from app.config import get_settings


@pytest.fixture(autouse=True)
def isolated_settings(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "test.db"))
    monkeypatch.setenv("VECTOR_STORE_PATH", str(tmp_path / "vectors.db"))
    monkeypatch.setenv("FILE_STORE_PATH", str(tmp_path / "files"))
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture(autouse=True)
def clear_caches():
    from app.infrastructure.cache import concept_cache, embedding_cache, prompt_cache, retrieval_cache
    for cache in (prompt_cache, embedding_cache, retrieval_cache, concept_cache):
        cache.clear()
    yield
    for cache in (prompt_cache, embedding_cache, retrieval_cache, concept_cache):
        cache.clear()


@pytest.fixture(autouse=True)
def bypass_auth_and_rate_limits():
    """Every existing test is testing business logic, not security --
    this keeps them all passing unchanged. test_security.py explicitly
    removes these overrides to test the real dependencies."""
    from app.main import app
    from app.security.auth import require_api_key
    from app.security.rate_limiter import rate_limit_dependency, reset_rate_limits

    app.dependency_overrides[require_api_key] = lambda: "test-key"
    app.dependency_overrides[rate_limit_dependency] = lambda: None
    reset_rate_limits()
    yield
    app.dependency_overrides.pop(require_api_key, None)
    app.dependency_overrides.pop(rate_limit_dependency, None)


@pytest.fixture(autouse=True)
def clear_trace_store():
    from app.infrastructure.observability import _current_trace_id, get_trace_store
    get_trace_store().clear()
    _current_trace_id.set(None)
    yield
    get_trace_store().clear()
    _current_trace_id.set(None)
