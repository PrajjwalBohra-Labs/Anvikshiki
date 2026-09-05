"""Align timestamp nullability with the ORM contract."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "0016_schema_alignment"
down_revision: str | None = "0015_source_ownership"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    for table in ("auth_sessions", "provenance_nodes", "provenance_edges"):
        op.alter_column(
            table,
            "created_at",
            existing_type=sa.DateTime(timezone=True),
            nullable=False,
        )


def downgrade() -> None:
    for table in ("auth_sessions", "provenance_nodes", "provenance_edges"):
        op.alter_column(
            table,
            "created_at",
            existing_type=sa.DateTime(timezone=True),
            nullable=True,
        )
