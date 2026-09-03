"""Add document versions, PDF pages, and extraction metadata.

Revision ID: 0006_document_ingestion_core
Revises: 0005_file_storage_foundation
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0006_document_ingestion_core"
down_revision: str | None = "0005_file_storage_foundation"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("documents", sa.Column("language", sa.String(length=32), nullable=True))
    op.add_column("documents", sa.Column("extraction_method", sa.String(length=64), nullable=True))
    op.add_column("documents", sa.Column("extraction_status", sa.String(length=32), nullable=True))
    op.add_column("documents", sa.Column("extraction_warnings", sa.JSON(), nullable=True))

    op.create_table(
        "document_versions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("document_id", sa.String(length=36), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("checksum_sha256", sa.String(length=64), nullable=False),
        sa.Column("original_filename", sa.String(length=512), nullable=False),
        sa.Column("mime_type", sa.String(length=128), nullable=False),
        sa.Column("storage_path", sa.String(length=1024), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("extraction_method", sa.String(length=64), nullable=False),
        sa.Column("extraction_status", sa.String(length=32), nullable=False),
        sa.Column("extraction_warnings", sa.JSON(), nullable=True),
        sa.Column("ingested_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("document_id", "version_number", name="uix_document_version_number"),
        sa.UniqueConstraint("checksum_sha256", name="uix_document_version_checksum"),
    )
    op.create_index("ix_document_versions_document_id", "document_versions", ["document_id"])
    op.create_index("ix_document_versions_checksum_sha256", "document_versions", ["checksum_sha256"])

    op.create_table(
        "pages",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("document_version_id", sa.String(length=36), nullable=False),
        sa.Column("page_number", sa.Integer(), nullable=False),
        sa.Column("page_order", sa.Integer(), nullable=False),
        sa.Column("extracted_text", sa.Text(), nullable=False),
        sa.Column("extraction_method", sa.String(length=64), nullable=False),
        sa.Column("extraction_status", sa.String(length=32), nullable=False),
        sa.Column("extraction_warnings", sa.JSON(), nullable=True),
        sa.ForeignKeyConstraint(["document_version_id"], ["document_versions.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("document_version_id", "page_number", name="uix_page_version_number"),
        sa.UniqueConstraint("document_version_id", "page_order", name="uix_page_version_order"),
    )
    op.create_index("ix_pages_document_version_id", "pages", ["document_version_id"])

    op.add_column("passages", sa.Column("document_version_id", sa.String(length=36), nullable=True))
    op.add_column("passages", sa.Column("page_id", sa.String(length=36), nullable=True))
    op.add_column("passages", sa.Column("passage_order", sa.Integer(), nullable=True))
    op.add_column("passages", sa.Column("extraction_method", sa.String(length=64), nullable=True))
    op.add_column("passages", sa.Column("section_heading", sa.String(length=512), nullable=True))
    op.create_index("ix_passages_document_version_id", "passages", ["document_version_id"])
    op.create_index("ix_passages_page_id", "passages", ["page_id"])
    op.create_foreign_key(
        "fk_passages_document_version_id",
        "passages",
        "document_versions",
        ["document_version_id"],
        ["id"],
    )
    op.create_foreign_key("fk_passages_page_id", "passages", "pages", ["page_id"], ["id"])


def downgrade() -> None:
    op.drop_constraint("fk_passages_page_id", "passages", type_="foreignkey")
    op.drop_constraint("fk_passages_document_version_id", "passages", type_="foreignkey")
    op.drop_index("ix_passages_page_id", table_name="passages")
    op.drop_index("ix_passages_document_version_id", table_name="passages")
    for column in ("section_heading", "extraction_method", "passage_order", "page_id", "document_version_id"):
        op.drop_column("passages", column)

    op.drop_index("ix_pages_document_version_id", table_name="pages")
    op.drop_table("pages")
    op.drop_index("ix_document_versions_checksum_sha256", table_name="document_versions")
    op.drop_index("ix_document_versions_document_id", table_name="document_versions")
    op.drop_table("document_versions")

    for column in ("extraction_warnings", "extraction_status", "extraction_method", "language"):
        op.drop_column("documents", column)
