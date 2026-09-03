"""Add durable user-owned records for the Step 43 memory foundation."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0013_memory_foundation"
down_revision: str | None = "0012_web_acquisition_metadata"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "memory_records",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("memory_tier", sa.String(length=32), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False, server_default="1.0"),
        sa.Column("provenance_source_id", sa.String(length=256), nullable=True),
        sa.Column("source_event", sa.String(length=256), nullable=False, server_default="interaction"),
        sa.Column("retention_policy", sa.String(length=32), nullable=False, server_default="durable"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_memory_records_user_id", "memory_records", ["user_id"])
    op.create_index("ix_memory_records_memory_tier", "memory_records", ["memory_tier"])
    op.create_index(
        "ix_memory_records_provenance_source_id",
        "memory_records",
        ["provenance_source_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_memory_records_provenance_source_id", table_name="memory_records")
    op.drop_index("ix_memory_records_memory_tier", table_name="memory_records")
    op.drop_index("ix_memory_records_user_id", table_name="memory_records")
    op.drop_table("memory_records")
