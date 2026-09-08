"""Align tradition/school uniqueness with the ORM constraints."""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0020_tradition_index_alignment"
down_revision: str | Sequence[str] | None = "0019_tradition_school_context"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(sa.text("DROP INDEX IF EXISTS ix_traditions_name"))
    op.execute(sa.text("DROP INDEX IF EXISTS ix_schools_name"))


def downgrade() -> None:
    op.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_traditions_name ON traditions (name)"))
    op.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_schools_name ON schools (name)"))
