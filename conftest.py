"""Explicit separation for PostgreSQL integration tests and SQLite tests."""

import os

import pytest


@pytest.fixture(autouse=True)
async def dispose_global_async_engine():
    """Prevent asyncpg connections crossing pytest event-loop boundaries."""
    yield
    from backend.app.infrastructure.database.session import engine

    await engine.dispose()


def pytest_collection_modifyitems(config, items):
    if os.environ.get("RUNTIME_PROFILE", "").strip().lower() != "test":
        return
    skip_postgres = pytest.mark.skip(
        reason="PostgreSQL integration test: run without RUNTIME_PROFILE=test against Docker PostgreSQL"
    )
    for item in items:
        if item.get_closest_marker("postgres"):
            item.add_marker(skip_postgres)


def pytest_configure(config):
    if os.environ.get("RUNTIME_PROFILE", "").strip().lower() == "test":
        os.environ.setdefault("AUTH_MODE", "test")
