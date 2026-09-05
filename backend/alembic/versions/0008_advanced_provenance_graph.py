"""Add the durable typed provenance graph."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0008_advanced_provenance_graph"
down_revision: str | None = "0007_ocr_page_metadata"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

node_type = sa.Enum(
    "SOURCE",
    "DOCUMENT",
    "DOCUMENT_VERSION",
    "PAGE",
    "PASSAGE",
    "CLAIM",
    "EVIDENCE",
    "SPECIALIST_ANALYSIS",
    "VALIDATION",
    "RESEARCH_RUN",
    "SYNTHESIS",
    name="provenancenodetype",
)
relation_type = sa.Enum(
    "CONTAINS",
    "HAS_VERSION",
    "SUPPORTS",
    "CONTRADICTS",
    "QUALIFIES",
    "CITES",
    "DERIVES_FROM",
    "VALIDATED_BY",
    "CONTRIBUTES_TO",
    "PRODUCES",
    "HAS_ANALYSIS",
    "HAS_VALIDATION",
    "HAS_EVIDENCE",
    "VALIDATES",
    name="provenancerelationtype",
)
node_type_column = postgresql.ENUM(
    "SOURCE",
    "DOCUMENT",
    "DOCUMENT_VERSION",
    "PAGE",
    "PASSAGE",
    "CLAIM",
    "EVIDENCE",
    "SPECIALIST_ANALYSIS",
    "VALIDATION",
    "RESEARCH_RUN",
    "SYNTHESIS",
    name="provenancenodetype",
    create_type=False,
)
relation_type_column = postgresql.ENUM(
    "CONTAINS",
    "HAS_VERSION",
    "SUPPORTS",
    "CONTRADICTS",
    "QUALIFIES",
    "CITES",
    "DERIVES_FROM",
    "VALIDATED_BY",
    "CONTRIBUTES_TO",
    "PRODUCES",
    "HAS_ANALYSIS",
    "HAS_VALIDATION",
    "HAS_EVIDENCE",
    "VALIDATES",
    name="provenancerelationtype",
    create_type=False,
)


def upgrade() -> None:
    bind = op.get_bind()
    node_type.create(bind, checkfirst=True)
    relation_type.create(bind, checkfirst=True)

    op.create_table(
        "provenance_nodes",
        sa.Column("id", sa.String(length=36), nullable=False),
    sa.Column("node_type", node_type_column, nullable=False),
        sa.Column("entity_id", sa.String(length=256), nullable=False),
        sa.Column("label", sa.String(length=512), nullable=False),
        sa.Column("metadata_payload", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("node_type", "entity_id", name="uix_provenance_node_identity"),
    )
    op.create_index("ix_provenance_nodes_node_type", "provenance_nodes", ["node_type"])

    op.create_table(
        "provenance_edges",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("from_node_id", sa.String(length=36), nullable=False),
        sa.Column("to_node_id", sa.String(length=36), nullable=False),
        sa.Column("relationship_type", relation_type_column, nullable=False),
        sa.Column("metadata_payload", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["from_node_id"], ["provenance_nodes.id"]),
        sa.ForeignKeyConstraint(["to_node_id"], ["provenance_nodes.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "from_node_id",
            "to_node_id",
            "relationship_type",
            name="uix_provenance_edge_identity",
        ),
    )
    op.create_index("ix_provenance_edges_from_node_id", "provenance_edges", ["from_node_id"])
    op.create_index("ix_provenance_edges_to_node_id", "provenance_edges", ["to_node_id"])
    op.create_index(
        "ix_provenance_edges_relationship_type", "provenance_edges", ["relationship_type"]
    )


def downgrade() -> None:
    op.drop_index("ix_provenance_edges_relationship_type", table_name="provenance_edges")
    op.drop_index("ix_provenance_edges_to_node_id", table_name="provenance_edges")
    op.drop_index("ix_provenance_edges_from_node_id", table_name="provenance_edges")
    op.drop_table("provenance_edges")
    op.drop_index("ix_provenance_nodes_node_type", table_name="provenance_nodes")
    op.drop_table("provenance_nodes")

    bind = op.get_bind()
    relation_type.drop(bind, checkfirst=True)
    node_type.drop(bind, checkfirst=True)
