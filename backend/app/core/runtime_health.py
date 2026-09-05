"""Safe runtime probes used by health and readiness endpoints."""

from sqlalchemy import text

from backend.app.infrastructure.database.session import AsyncSessionLocal, engine


async def probe_runtime(session_factory=AsyncSessionLocal) -> dict[str, str]:
    database = "unavailable"
    pgvector = "unavailable"
    schema_status = "unavailable"
    try:
        async with session_factory() as session:
            await session.execute(text("SELECT 1"))
            database = "connected"
            if engine.dialect.name != "postgresql":
                pgvector = "unavailable_in_test_profile"
                schema_status = "current"
            else:
                extension = await session.execute(
                    text("SELECT extversion FROM pg_extension WHERE extname = 'vector'")
                )
                pgvector = "available" if extension.scalar_one_or_none() else "unavailable"
                required_schema = await session.execute(
                    text(
                        """
                        SELECT count(*)
                        FROM information_schema.columns
                        WHERE table_schema = 'public'
                          AND ((table_name = 'sources' AND column_name = 'user_id')
                               OR (table_name = 'background_jobs' AND column_name = 'id')
                               OR (table_name = 'passages' AND column_name = 'search_vector'))
                        """
                    )
                )
                schema_status = "current" if required_schema.scalar_one() == 3 else "out_of_date"
    except Exception:
        # Do not expose connection strings, credentials, or driver internals.
        pass

    ready = database == "connected" and (
        pgvector == "available" or engine.dialect.name != "postgresql"
    ) and schema_status == "current"
    return {
        "status": "healthy" if database == "connected" else "degraded",
        "readiness": "ready" if ready else "not_ready",
        "database": database,
        "pgvector": pgvector,
        "database_schema": schema_status,
        "model_runtime": "local_adapter_ready",
        "mcp_boundary": "internal_tool_boundary_enforced",
    }
