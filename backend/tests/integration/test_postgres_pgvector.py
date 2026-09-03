import pytest
from pgvector.sqlalchemy import Vector
from sqlalchemy import Column, Integer, MetaData, Table, Text, select, text

from backend.app.infrastructure.database.models import PassageModel
from backend.app.infrastructure.database.session import engine

pytestmark = pytest.mark.postgres


def _vector(first: float, second: float = 0.0) -> list[float]:
    """Build a fixed 384-dimensional test vector, not an embedding fallback."""
    return [first, second] + [0.0] * 382


@pytest.mark.asyncio
async def test_postgresql_pgvector_distance_ranks_inside_database() -> None:
    """Prove that PostgreSQL, not Python, executes cosine-distance ranking."""
    if engine.dialect.name != "postgresql":
        pytest.fail(f"PostgreSQL integration test refuses dialect: {engine.dialect.name}")

    passage_embedding_type = PassageModel.__table__.c.embedding.type
    assert isinstance(passage_embedding_type, Vector)
    assert passage_embedding_type.dim == 384

    metadata = MetaData()
    verification_table = Table(
        "pgvector_verification_passages",
        metadata,
        Column("id", Integer, primary_key=True),
        Column("content", Text, nullable=False),
        Column("embedding", Vector(384), nullable=False),
    )
    table_created = False

    try:
        try:
            async with engine.begin() as connection:
                await connection.execute(text("SELECT 1"))
                await connection.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))

                server = (
                    await connection.execute(
                        text(
                            "SELECT version(), current_database(), "
                            "(SELECT extversion FROM pg_extension WHERE extname = 'vector')"
                        )
                    )
                ).one()
                assert server[2], "The vector extension is not enabled in this database"

                await connection.run_sync(verification_table.create)
                table_created = True
                await connection.execute(
                    verification_table.insert(),
                    [
                        {"id": 1, "content": "exact nearest", "embedding": _vector(1.0)},
                        {"id": 2, "content": "near vector", "embedding": _vector(0.9, 0.1)},
                        {"id": 3, "content": "opposite vector", "embedding": _vector(-1.0)},
                    ],
                )

                distance = verification_table.c.embedding.cosine_distance(
                    _vector(1.0)
                ).label("cosine_distance")
                statement = (
                    select(verification_table.c.id, verification_table.c.content, distance)
                    .order_by(distance, verification_table.c.id)
                )
                compiled_sql = str(
                    statement.compile(dialect=engine.sync_engine.dialect)
                )
                assert "<=>" in compiled_sql

                column_type = (
                    await connection.execute(
                        text(
                            "SELECT format_type(a.atttypid, a.atttypmod) "
                            "FROM pg_attribute a "
                            "JOIN pg_class c ON c.oid = a.attrelid "
                            "WHERE c.relname = 'pgvector_verification_passages' "
                            "AND a.attname = 'embedding'"
                        )
                    )
                ).scalar_one()
                assert column_type == "vector(384)"

                ranked_rows = (await connection.execute(statement)).all()
                assert [row.id for row in ranked_rows] == [1, 2, 3]
                assert ranked_rows[0].cosine_distance < ranked_rows[1].cosine_distance
                assert ranked_rows[1].cosine_distance < ranked_rows[2].cosine_distance

                print(f"PostgreSQL: {server[0]}")
                print(f"Database: {server[1]}")
                print(f"pgvector: {server[2]}")
                print(f"Embedding column: {column_type}")
                print(f"Executed SQL: {compiled_sql}")
                print(f"Database ranking: {[row.id for row in ranked_rows]}")
        except Exception as exc:
            pytest.fail(
                "PostgreSQL + pgvector prerequisite or query execution failed: "
                f"{type(exc).__name__}: {exc}"
            )
    finally:
        if table_created:
            async with engine.begin() as connection:
                await connection.run_sync(
                    lambda sync_connection: verification_table.drop(
                        sync_connection, checkfirst=True
                    )
                )
