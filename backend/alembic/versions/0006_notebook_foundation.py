"""Create durable user-owned notebooks for Step 55.

Revision ID: 0006_notebook_foundation
Revises: 0005_file_storage_foundation
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "0006_notebook_foundation"
down_revision: str | None = "0005_file_storage_foundation"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "notebooks",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("title", sa.String(length=256), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_notebooks_user_id", "notebooks", ["user_id"], unique=False)
    op.create_index("ix_notebooks_user_updated", "notebooks", ["user_id", "updated_at"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_notebooks_user_updated", table_name="notebooks")
    op.drop_index("ix_notebooks_user_id", table_name="notebooks")
    op.drop_table("notebooks")
