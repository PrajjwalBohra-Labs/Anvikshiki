"""Persist reproducible metadata for acquired web documents."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "0012_web_acquisition_metadata"
down_revision: str | None = "0011_ocr_text_and_confidence"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("documents", sa.Column("web_metadata", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("documents", "web_metadata")
