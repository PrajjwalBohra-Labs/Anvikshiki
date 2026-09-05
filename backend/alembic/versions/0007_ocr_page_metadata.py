"""Add page-level OCR metadata without replacing native extraction."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0007_ocr_page_metadata"
down_revision: str | None = "0006_document_ingestion_core"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("pages", sa.Column("native_extracted_text", sa.Text(), nullable=True))
    op.add_column("pages", sa.Column("ocr_status", sa.String(length=32), nullable=True))
    op.add_column("pages", sa.Column("ocr_language", sa.String(length=128), nullable=True))
    op.add_column("pages", sa.Column("ocr_dpi", sa.Integer(), nullable=True))
    op.add_column("pages", sa.Column("ocr_text_length", sa.Integer(), nullable=True))
    op.add_column("pages", sa.Column("ocr_processed_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("pages", sa.Column("ocr_error", sa.Text(), nullable=True))


def downgrade() -> None:
    for column in (
        "ocr_error",
        "ocr_processed_at",
        "ocr_text_length",
        "ocr_dpi",
        "ocr_language",
        "ocr_status",
        "native_extracted_text",
    ):
        op.drop_column("pages", column)
