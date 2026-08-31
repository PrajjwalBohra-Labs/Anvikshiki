"""Persist OCR text and page confidence without replacing native extraction."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "0011_ocr_text_and_confidence"
down_revision: str | None = "0010_lexical_search"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("pages", sa.Column("ocr_text", sa.Text(), nullable=True))
    op.add_column("pages", sa.Column("ocr_confidence", sa.Float(), nullable=True))


def downgrade() -> None:
    op.drop_column("pages", "ocr_confidence")
    op.drop_column("pages", "ocr_text")
