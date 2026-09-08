"""Persist inquiry-local reasoning artifacts without merging them into knowledge.

The existing claims, evidence, source, and provenance tables remain the
authoritative source-side records.  These tables hold the run-scoped
interpretations, plans, comparisons, inferences, synthesis, challenges, and
typed reasoning graph required to audit how an answer was constructed.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "0018_reasoning_artifacts"
down_revision: str | Sequence[str] | None = "0017_lexical_alignment"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


QUESTION_COLUMNS = (
    ("normalized_question", sa.Text()),
    ("interpreted_question", sa.Text()),
    ("primary_intent", sa.String(128)),
    ("secondary_intents", sa.JSON()),
    ("intellectual_tasks", sa.JSON()),
    ("concepts", sa.JSON()),
    ("traditions", sa.JSON()),
    ("schools", sa.JSON()),
    ("disciplines", sa.JSON()),
    ("assumptions", sa.JSON()),
    ("presuppositions", sa.JSON()),
    ("ambiguities", sa.JSON()),
    ("temporal_scope", sa.String(256)),
    ("textual_scope", sa.String(512)),
    ("geographical_scope", sa.String(256)),
    ("requested_depth", sa.String(32)),
    ("expected_answer_form", sa.String(128)),
    ("research_requirement", sa.Text()),
    ("evidence_requirement", sa.Text()),
    ("interpretation_confidence", sa.Float()),
    ("alternative_interpretations", sa.JSON()),
)


def _json(name: str) -> sa.Column:
    return sa.Column(name, sa.JSON(), nullable=True)


def _run_fk() -> sa.ForeignKey:
    return sa.ForeignKey("research_runs.id", ondelete="CASCADE")


def upgrade() -> None:
    for name, column_type in QUESTION_COLUMNS:
        op.add_column("research_questions", sa.Column(name, column_type, nullable=True))

    op.create_table(
        "reasoning_interpretations",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("run_id", sa.String(36), _run_fk(), nullable=False),
        sa.Column("formulation", sa.Text(), nullable=False),
        sa.Column("interpretation_type", sa.String(64), nullable=False, server_default="ALTERNATIVE"),
        _json("assumptions"), _json("concepts"), _json("evidence_ids"), _json("implications"),
        sa.Column("confidence", sa.Float(), nullable=False, server_default="0"),
        sa.Column("epistemic_state", sa.String(32), nullable=False, server_default="INTERPRETIVE"),
        _json("unresolved_issues"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_reasoning_interpretations_run_id", "reasoning_interpretations", ["run_id"])

    op.create_table(
        "research_directions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("run_id", sa.String(36), _run_fk(), nullable=False),
        sa.Column("research_question", sa.Text(), nullable=False),
        sa.Column("purpose", sa.Text(), nullable=False),
        sa.Column("expected_evidence", sa.Text(), nullable=False),
        _json("search_strategy"), _json("source_types"), _json("traditions"), _json("concepts"),
        _json("exclusions"), _json("completion_criteria"), _json("discovered_evidence"),
        _json("evidence_gaps"), _json("dependencies"),
        sa.Column("priority", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("revision", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("status", sa.String(32), nullable=False, server_default="PLANNED"),
    )
    op.create_index("ix_research_directions_run_id", "research_directions", ["run_id"])

    op.create_table(
        "source_positions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("run_id", sa.String(36), _run_fk(), nullable=False),
        sa.Column("source_id", sa.String(36), sa.ForeignKey("sources.id", ondelete="SET NULL"), nullable=True),
        sa.Column("source_title", sa.String(512), nullable=False),
        sa.Column("position_type", sa.String(32), nullable=False, server_default="RECONSTRUCTED_POSITION"),
        sa.Column("central_thesis", sa.Text(), nullable=False),
        _json("propositions"), _json("definitions"), _json("conceptual_commitments"), _json("arguments"),
        _json("evidence_passage_ids"), _json("assumptions"), _json("qualifications"), _json("limitations"),
        _json("interpretive_uncertainties"),
        sa.Column("confidence", sa.Float(), nullable=False, server_default="0"),
        sa.Column("epistemic_state", sa.String(32), nullable=False, server_default="INTERPRETIVE"),
    )
    op.create_index("ix_source_positions_run_id", "source_positions", ["run_id"])
    op.create_index("ix_source_positions_source_id", "source_positions", ["source_id"])

    op.create_table(
        "reasoning_relationships",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("run_id", sa.String(36), _run_fk(), nullable=False),
        sa.Column("source_a_id", sa.String(36), nullable=True),
        sa.Column("source_b_id", sa.String(36), nullable=True),
        sa.Column("source_a_label", sa.String(512), nullable=False),
        sa.Column("source_b_label", sa.String(512), nullable=False),
        sa.Column("relationship_type", sa.String(32), nullable=False),
        sa.Column("classification", sa.String(64), nullable=False, server_default="UNRESOLVED"),
        sa.Column("justification", sa.Text(), nullable=False),
        _json("supporting_passage_ids"),
        sa.Column("confidence", sa.Float(), nullable=False, server_default="0"),
        sa.Column("uncertainty", sa.Text(), nullable=True),
        sa.Column("scope", sa.Text(), nullable=True),
    )
    op.create_index("ix_reasoning_relationships_run_id", "reasoning_relationships", ["run_id"])
    op.create_index("ix_reasoning_relationships_source_a_id", "reasoning_relationships", ["source_a_id"])
    op.create_index("ix_reasoning_relationships_source_b_id", "reasoning_relationships", ["source_b_id"])

    for table, columns in {
        "inferences": [
            sa.Column("conclusion", sa.Text(), nullable=False), _json("premise_claim_ids"), _json("evidence_ids"),
            sa.Column("reasoning_basis", sa.Text(), nullable=False), _json("assumptions"), _json("alternatives"),
            _json("counterarguments"), sa.Column("confidence", sa.Float(), nullable=False, server_default="0"),
            sa.Column("epistemic_state", sa.String(32), nullable=False, server_default="INFERENTIAL"),
        ],
        "syntheses": [
            sa.Column("statement", sa.Text(), nullable=False), _json("contributing_claim_ids"),
            _json("contributing_source_position_ids"), _json("contributing_relationship_ids"),
            sa.Column("reasoning_basis", sa.Text(), nullable=False), _json("unresolved_tensions"),
            _json("alternative_synthesis"), _json("limitations"),
            sa.Column("confidence", sa.Float(), nullable=False, server_default="0"),
            sa.Column("epistemic_state", sa.String(32), nullable=False, server_default="INFERENTIAL"),
        ],
        "insights": [
            sa.Column("statement", sa.Text(), nullable=False), sa.Column("insight_type", sa.String(64), nullable=False),
            _json("originating_claim_ids"), _json("source_basis"), sa.Column("reasoning_basis", sa.Text(), nullable=False),
            sa.Column("confidence", sa.Float(), nullable=False, server_default="0"),
            sa.Column("epistemic_state", sa.String(32), nullable=False, server_default="INTERPRETIVE"),
        ],
    }.items():
        op.create_table(
            table,
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("run_id", sa.String(36), _run_fk(), nullable=False),
            *columns,
        )
        op.create_index(f"ix_{table}_run_id", table, ["run_id"])

    op.create_table(
        "reasoning_challenges",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("run_id", sa.String(36), _run_fk(), nullable=False),
        sa.Column("target_type", sa.String(64), nullable=False),
        sa.Column("target_id", sa.String(36), nullable=True),
        sa.Column("issue_type", sa.String(64), nullable=False),
        sa.Column("statement", sa.Text(), nullable=False),
        _json("evidence_ids"), sa.Column("alternative_interpretation", sa.Text()),
        sa.Column("severity", sa.String(32), nullable=False, server_default="MATERIAL"),
        sa.Column("resolution", sa.String(32), nullable=False, server_default="UNRESOLVED"),
        sa.Column("confidence", sa.Float(), nullable=False, server_default="0"),
    )
    op.create_index("ix_reasoning_challenges_run_id", "reasoning_challenges", ["run_id"])
    op.create_index("ix_reasoning_challenges_target_id", "reasoning_challenges", ["target_id"])

    node_types = sa.Enum(
        "QUESTION", "PROBLEM", "INTERPRETATION", "CONCEPT", "TRADITION", "SOURCE", "PASSAGE",
        "POSITION", "ARGUMENT", "PREMISE", "CLAIM", "EVIDENCE", "INFERENCE", "SYNTHESIS",
        "INSIGHT", "COUNTERARGUMENT", "RESEARCH_DIRECTION", name="reasoningnodetype",
    )
    relation_types = sa.Enum(
        "ASKS", "REFINES", "CONTAINS", "INVOLVES", "BELONGS_TO", "DEFINED_BY", "APPEARS_IN",
        "SUPPORTS", "CONTRADICTS", "QUALIFIES", "COMPLEMENTS", "REINTERPRETS", "CRITIQUES",
        "PRESUPPOSES", "DERIVES_FROM", "INFERRED_FROM", "SYNTHESIZES", "CHALLENGES",
        "ALTERNATIVE_TO", "LEAVES_UNRESOLVED", name="reasoningrelationtype",
    )
    op.create_table(
        "reasoning_nodes",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("run_id", sa.String(36), _run_fk(), nullable=False),
        sa.Column("node_type", node_types, nullable=False),
        sa.Column("entity_id", sa.String(36), nullable=False),
        sa.Column("label", sa.String(512), nullable=False),
        _json("metadata_payload"),
        sa.UniqueConstraint("run_id", "node_type", "entity_id", name="uix_reasoning_node_identity"),
    )
    op.create_index("ix_reasoning_nodes_run_id", "reasoning_nodes", ["run_id"])
    op.create_index("ix_reasoning_nodes_node_type", "reasoning_nodes", ["node_type"])
    op.create_table(
        "reasoning_edges",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("run_id", sa.String(36), _run_fk(), nullable=False),
        sa.Column("from_node_id", sa.String(36), sa.ForeignKey("reasoning_nodes.id", ondelete="CASCADE"), nullable=False),
        sa.Column("to_node_id", sa.String(36), sa.ForeignKey("reasoning_nodes.id", ondelete="CASCADE"), nullable=False),
        sa.Column("relationship_type", relation_types, nullable=False),
        sa.Column("justification", sa.Text()),
        sa.Column("confidence", sa.Float(), nullable=False, server_default="0"),
        _json("metadata_payload"),
        sa.UniqueConstraint("run_id", "from_node_id", "to_node_id", "relationship_type", name="uix_reasoning_edge_identity"),
    )
    op.create_index("ix_reasoning_edges_run_id", "reasoning_edges", ["run_id"])
    op.create_index("ix_reasoning_edges_from_node_id", "reasoning_edges", ["from_node_id"])
    op.create_index("ix_reasoning_edges_to_node_id", "reasoning_edges", ["to_node_id"])
    op.create_index("ix_reasoning_edges_relationship_type", "reasoning_edges", ["relationship_type"])


def downgrade() -> None:
    for table in ("reasoning_edges", "reasoning_nodes", "reasoning_challenges", "insights", "syntheses", "inferences", "reasoning_relationships", "source_positions", "research_directions", "reasoning_interpretations"):
        op.drop_table(table)
    for name, _column_type in reversed(QUESTION_COLUMNS):
        op.drop_column("research_questions", name)
