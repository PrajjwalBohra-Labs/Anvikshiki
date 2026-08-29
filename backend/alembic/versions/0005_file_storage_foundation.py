"""Persist original file size for the local storage foundation.

Revision ID: 0005_file_storage_foundation
Revises: 0004_auth_sessions
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "0005_file_storage_foundation"
down_revision: str | None = "0004_auth_sessions"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Nullable preserves existing document rows created before file-size
    # persistence was introduced. New ingestion records populate this field.
    op.add_column("documents", sa.Column("size_bytes", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("documents", "size_bytes")
