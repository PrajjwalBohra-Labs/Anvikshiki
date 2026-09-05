"""Align creation timestamp nullability with the ORM models.

Revision ID: 0015_model_alignment
Revises: 0014_background_jobs
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0015_model_alignment"
down_revision: str | None = "0014_background_jobs"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


_TABLES = ("auth_sessions", "provenance_nodes", "provenance_edges")


def upgrade() -> None:
    # Older revisions allowed these timestamps to be null. Backfill before
    # enforcing the invariant so upgrades remain safe for existing databases.
    for table_name in _TABLES:
        op.execute(
            sa.text(
                f"UPDATE {table_name} "
                "SET created_at = CURRENT_TIMESTAMP WHERE created_at IS NULL"
            )
        )
        op.alter_column(table_name, "created_at", nullable=False)


def downgrade() -> None:
    for table_name in _TABLES:
        op.alter_column(table_name, "created_at", nullable=True)
