"""Merge schema branches and repair derived PostgreSQL lexical indexing."""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0017_lexical_alignment"
down_revision: tuple[str, str] = ("0016_schema_alignment", "0016_merge_schema_heads")
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
    op.execute(
        sa.text(
            "CREATE INDEX IF NOT EXISTS ix_passages_embedding_status "
            "ON passages (embedding_status)"
        )
    )

    # Some development databases were provisioned from ORM metadata before
    # the migration ledger existed.  Bring those additive/default/constraint
    # details in line before a safe baseline stamp; all operations are
    # conditional or idempotent for databases migrated from 0001-0016.
    op.execute(
        sa.text(
            "ALTER TABLE memory_records "
            "ALTER COLUMN confidence SET DEFAULT 1.0, "
            "ALTER COLUMN source_event SET DEFAULT 'interaction', "
            "ALTER COLUMN retention_policy SET DEFAULT 'durable'"
        )
    )
    for table, old_name, new_name in (
        ("claims", "claims_research_run_id_fkey", "fk_claims_research_run_id_runs"),
        (
            "research_runs",
            "research_runs_research_question_id_fkey",
            "fk_research_runs_research_question_id_questions",
        ),
        (
            "passages",
            "passages_document_version_id_fkey",
            "fk_passages_document_version_id",
        ),
        ("passages", "passages_page_id_fkey", "fk_passages_page_id"),
    ):
        op.execute(
            sa.text(
                f"DO $$ BEGIN "
                f"IF EXISTS (SELECT 1 FROM pg_constraint WHERE conname = '{old_name}') "
                f"AND NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = '{new_name}') "
                f"THEN ALTER TABLE {table} RENAME CONSTRAINT {old_name} TO {new_name}; "
                f"END IF; END $$"
            )
        )


def downgrade() -> None:
    # The lexical objects are owned by the original 0010 migration.  This
    # repair must not remove them from a database that still depends on them.
    pass
