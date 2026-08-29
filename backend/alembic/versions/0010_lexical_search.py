"""Add trigger-maintained PostgreSQL lexical search over passages."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "0010_lexical_search"
down_revision: str | None = "0009_embedding_index_metadata"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "passages", sa.Column("search_vector", postgresql.TSVECTOR(), nullable=True)
    )
    op.execute(
        sa.text(
            "UPDATE passages SET search_vector = "
            "to_tsvector('simple'::regconfig, coalesce(content, ''))"
        )
    )
    op.execute(
        sa.text(
            """
            CREATE FUNCTION passages_search_vector_refresh() RETURNS trigger
            LANGUAGE plpgsql AS $$
            BEGIN
                NEW.search_vector := to_tsvector('simple'::regconfig, coalesce(NEW.content, ''));
                RETURN NEW;
            END;
            $$
            """
        )
    )
    op.execute(
        sa.text(
            """
            CREATE TRIGGER passages_search_vector_refresh_trigger
            BEFORE INSERT OR UPDATE OF content ON passages
            FOR EACH ROW EXECUTE FUNCTION passages_search_vector_refresh()
            """
        )
    )
    op.create_index(
        "ix_passages_search_vector",
        "passages",
        ["search_vector"],
        postgresql_using="gin",
    )


def downgrade() -> None:
    op.drop_index("ix_passages_search_vector", table_name="passages")
    op.execute(
        sa.text("DROP TRIGGER passages_search_vector_refresh_trigger ON passages")
    )
    op.execute(sa.text("DROP FUNCTION passages_search_vector_refresh()"))
    op.drop_column("passages", "search_vector")
