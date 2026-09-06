"""Shared test-database setup for PostgreSQL-backed integration fixtures."""

from collections.abc import AsyncIterator

import pytest
from sqlalchemy import DDL, event, text

from backend.app.core.config import RuntimeProfile, settings
from backend.app.infrastructure.database.models import PassageModel
from backend.app.infrastructure.database.session import engine


def _split_lexical_ddl() -> tuple[DDL, DDL, DDL, DDL]:
    """Install one-statement listeners so asyncpg can prepare each DDL safely."""
    original = next(
        listener
        for listener in PassageModel.__table__.dispatch.after_create.listeners
        if isinstance(listener, DDL)
        and "passages_search_vector_refresh" in listener.statement
        and "CREATE TRIGGER" in listener.statement
    )
    event.remove(PassageModel.__table__, "after_create", original)

    function_ddl = DDL(
        """
        CREATE OR REPLACE FUNCTION passages_search_vector_refresh() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
            NEW.search_vector := to_tsvector('simple'::regconfig, coalesce(NEW.content, ''));
            RETURN NEW;
        END;
        $$
        """
    ).execute_if(dialect="postgresql")
    drop_trigger_ddl = DDL(
        "DROP TRIGGER IF EXISTS passages_search_vector_refresh_trigger ON passages"
    ).execute_if(dialect="postgresql")
    create_trigger_ddl = DDL(
        """
        CREATE TRIGGER passages_search_vector_refresh_trigger
        BEFORE INSERT OR UPDATE OF content ON passages
        FOR EACH ROW EXECUTE FUNCTION passages_search_vector_refresh()
        """
    ).execute_if(dialect="postgresql")

    for statement in (function_ddl, drop_trigger_ddl, create_trigger_ddl):
        event.listen(PassageModel.__table__, "after_create", statement)
    return original, function_ddl, drop_trigger_ddl, create_trigger_ddl


@pytest.fixture(autouse=True)
async def postgres_lexical_ddl() -> AsyncIterator[None]:
    """Keep direct metadata-created test schemas compatible with asyncpg."""
    original, *statements = _split_lexical_ddl()
    previous_profile = settings.RUNTIME_PROFILE
    previous_auth_mode = settings.AUTH_MODE
    try:
        if engine.dialect.name == "postgresql":
            # These legacy API fixtures intentionally omit bearer headers. Keep
            # their explicit test-auth contract while retaining PostgreSQL and
            # pgvector for the database path under test.
            settings.RUNTIME_PROFILE = RuntimeProfile.TEST
            settings.AUTH_MODE = "test"
            async with engine.begin() as connection:
                await connection.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        yield
    finally:
        settings.RUNTIME_PROFILE = previous_profile
        settings.AUTH_MODE = previous_auth_mode
        for statement in statements:
            event.remove(PassageModel.__table__, "after_create", statement)
        event.listen(PassageModel.__table__, "after_create", original)
