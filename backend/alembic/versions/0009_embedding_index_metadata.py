"""Add reproducible lifecycle metadata for passage embeddings."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "0009_embedding_index_metadata"
down_revision: str | None = "0008_advanced_provenance_graph"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


embedding_status = sa.Enum(
    "PENDING", "INDEXING", "INDEXED", "FAILED", name="embeddingindexstatus"
)
embedding_status_column = postgresql.ENUM(
    "PENDING",
    "INDEXING",
    "INDEXED",
    "FAILED",
    name="embeddingindexstatus",
    create_type=False,
)


def upgrade() -> None:
    bind = op.get_bind()
    embedding_status.create(bind, checkfirst=True)

    op.add_column("passages", sa.Column("embedding_provider", sa.String(length=64)))
    op.add_column("passages", sa.Column("embedding_model_version", sa.String(length=128)))
    op.add_column("passages", sa.Column("embedding_dimension", sa.Integer()))
    op.add_column(
        "passages", sa.Column("embedding_config_fingerprint", sa.String(length=64))
    )
    op.add_column("passages", sa.Column("embedding_content_sha256", sa.String(length=64)))
    op.add_column(
        "passages",
        sa.Column("embedding_generated_at", sa.DateTime(timezone=True)),
    )
    op.add_column(
        "passages",
        sa.Column("embedding_status", embedding_status_column, nullable=True),
    )
    op.add_column("passages", sa.Column("embedding_error", sa.Text()))

    op.execute(
        sa.text(
            "UPDATE passages SET embedding_status = "
            "CASE WHEN embedding IS NULL THEN 'PENDING'::embeddingindexstatus "
            "ELSE 'INDEXED'::embeddingindexstatus END, "
            "embedding_dimension = CASE WHEN embedding IS NULL THEN NULL ELSE 384 END, "
            "embedding_model_version = embedding_model"
        )
    )
    op.alter_column("passages", "embedding_status", nullable=False)
    op.create_index(
        "ix_passages_embedding_status", "passages", ["embedding_status"]
    )
    op.create_index(
        "ix_passages_embedding_config_fingerprint",
        "passages",
        ["embedding_config_fingerprint"],
    )
    op.create_index(
        "ix_passages_embedding_content_sha256",
        "passages",
        ["embedding_content_sha256"],
    )


def downgrade() -> None:
    op.drop_index("ix_passages_embedding_content_sha256", table_name="passages")
    op.drop_index("ix_passages_embedding_config_fingerprint", table_name="passages")
    op.drop_index("ix_passages_embedding_status", table_name="passages")
    op.drop_column("passages", "embedding_error")
    op.drop_column("passages", "embedding_status")
    op.drop_column("passages", "embedding_generated_at")
    op.drop_column("passages", "embedding_content_sha256")
    op.drop_column("passages", "embedding_config_fingerprint")
    op.drop_column("passages", "embedding_dimension")
    op.drop_column("passages", "embedding_model_version")
    op.drop_column("passages", "embedding_provider")

    bind = op.get_bind()
    embedding_status.drop(bind, checkfirst=True)
