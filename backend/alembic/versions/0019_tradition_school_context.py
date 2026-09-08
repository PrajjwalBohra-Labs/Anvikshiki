"""Persist traditions, schools, and context-sensitive concept identity."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "0019_tradition_school_context"
down_revision: str | Sequence[str] | None = "0018_reasoning_artifacts"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "traditions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(256), nullable=False),
        sa.Column("parent_tradition_id", sa.String(36), sa.ForeignKey("traditions.id", ondelete="SET NULL")),
        sa.Column("historical_period", sa.String(256)),
        sa.Column("conceptual_commitments", sa.JSON()),
        sa.Column("terminology", sa.JSON()),
        sa.Column("interpretive_notes", sa.JSON()),
        sa.UniqueConstraint("name", name="uix_traditions_name"),
    )
    op.create_index("ix_traditions_parent_tradition_id", "traditions", ["parent_tradition_id"])
    op.create_table(
        "schools",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tradition_id", sa.String(36), sa.ForeignKey("traditions.id", ondelete="SET NULL")),
        sa.Column("name", sa.String(256), nullable=False),
        sa.Column("subschool", sa.String(256)),
        sa.Column("historical_period", sa.String(256)),
        sa.Column("conceptual_commitments", sa.JSON()),
        sa.Column("internal_disagreements", sa.JSON()),
        sa.UniqueConstraint("name", name="uix_schools_name"),
    )
    op.create_index("ix_schools_tradition_id", "schools", ["tradition_id"])
    op.add_column("sources", sa.Column("tradition_id", sa.String(36), sa.ForeignKey("traditions.id", ondelete="SET NULL")))
    op.add_column("sources", sa.Column("school_id", sa.String(36), sa.ForeignKey("schools.id", ondelete="SET NULL")))
    op.create_index("ix_sources_tradition_id", "sources", ["tradition_id"])
    op.create_index("ix_sources_school_id", "sources", ["school_id"])
    for name, column_type in (
        ("tradition_id", sa.String(36)), ("school_id", sa.String(36)),
        ("textual_context", sa.Text()), ("technical_meaning", sa.Text()),
        ("contextual_meaning", sa.Text()), ("theoretical_role", sa.Text()),
        ("historical_development", sa.Text()), ("interpretive_uncertainty", sa.Text()),
        ("provenance_payload", sa.JSON()),
    ):
        foreign_key = sa.ForeignKey("traditions.id", ondelete="SET NULL") if name == "tradition_id" else sa.ForeignKey("schools.id", ondelete="SET NULL") if name == "school_id" else None
        op.add_column("concepts", sa.Column(name, column_type, foreign_key, nullable=True))
    op.create_index("ix_concepts_tradition_id", "concepts", ["tradition_id"])
    op.create_index("ix_concepts_school_id", "concepts", ["school_id"])


def downgrade() -> None:
    op.drop_index("ix_concepts_school_id", table_name="concepts")
    op.drop_index("ix_concepts_tradition_id", table_name="concepts")
    for name in ("provenance_payload", "interpretive_uncertainty", "historical_development", "theoretical_role", "contextual_meaning", "technical_meaning", "textual_context", "school_id", "tradition_id"):
        op.drop_column("concepts", name)
    op.drop_index("ix_sources_school_id", table_name="sources")
    op.drop_index("ix_sources_tradition_id", table_name="sources")
    op.drop_column("sources", "school_id")
    op.drop_column("sources", "tradition_id")
    op.drop_table("schools")
    op.drop_table("traditions")
