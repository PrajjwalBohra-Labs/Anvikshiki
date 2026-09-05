"""Repair derived PostgreSQL lexical indexing for manually provisioned databases."""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0017_lexical_alignment"
down_revision: str | None = "0016_schema_alignment"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 0010 creates these objects on a clean migration path.  This repair is
    # idempotent for databases provisioned from Base.metadata or older heads.
    op.execute(
        sa.text(
            """
            CREATE OR REPLACE FUNCTION passages_search_vector_refresh() RETURNS trigger
            LANGUAGE plpgsql AS $$
            BEGIN
                NEW.search_vector := to_tsvector(
                    'simple'::regconfig, coalesce(NEW.content, '')
                );
                RETURN NEW;
            END;
            $$;
            """
        )
    )
    op.execute(
        sa.text(
            """
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM pg_trigger
                    WHERE tgrelid = 'passages'::regclass
                      AND tgname = 'passages_search_vector_refresh_trigger'
                ) THEN
                    CREATE TRIGGER passages_search_vector_refresh_trigger
                    BEFORE INSERT OR UPDATE OF content ON passages
                    FOR EACH ROW EXECUTE FUNCTION passages_search_vector_refresh();
                END IF;
            END $$;
            """
        )
    )
    op.execute(
        sa.text(
            """
            UPDATE passages
            SET search_vector = to_tsvector('simple'::regconfig, coalesce(content, ''))
            WHERE search_vector IS NULL;
            """
        )
    )
    op.execute(
        sa.text(
            "CREATE INDEX IF NOT EXISTS ix_passages_search_vector "
            "ON passages USING gin (search_vector)"
        )
    )


def downgrade() -> None:
    # The lexical objects are owned by the original 0010 migration.  This
    # repair must not remove them from a database that still depends on them.
    pass
