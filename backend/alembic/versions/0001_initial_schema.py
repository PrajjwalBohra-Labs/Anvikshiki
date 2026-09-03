"""Create the current Anvikshiki schema.

Revision ID: 0001_initial_schema
Revises:
Create Date: 2026-08-25
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector

revision: str = "0001_initial_schema"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


source_type = sa.Enum(
    "PRIMARY", "SECONDARY", "TRANSLATION", "COMMENTARY", "DISCOVERY_ONLY", "UNVERIFIED",
    name="sourcetype",
)
source_relationship_type = sa.Enum(
    "TRANSLATION_OF", "COMMENTARY_ON", "INTERPRETATION_OF", "EDITION_OF",
    name="sourcerelationshiptype",
)
claim_type = sa.Enum(
    "DIRECT_SOURCE_CLAIM", "TRANSLATION", "SCHOLARLY_INTERPRETATION", "SCIENTIFIC_FINDING",
    "MODEL_SYNTHESIS", "INFERENCE", "ANALOGY", "HYPOTHESIS", "SPECULATION", "UNCERTAIN",
    name="claimtype",
)
relation_type = sa.Enum("SUPPORTS", "CONTRADICTS", "QUALIFIES", name="relationtype")
evidence_status = sa.Enum(
    "SUPPORTED", "PLAUSIBLE", "CONTESTED", "WEAKLY_SUPPORTED", "UNRESOLVED",
    "INSUFFICIENT_EVIDENCE",
    name="evidencestatus",
)


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        "arguments",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("title", sa.String(256), nullable=False),
        sa.Column("conclusion_statement", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "claims",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("statement", sa.Text(), nullable=False),
        sa.Column("claim_type", claim_type, nullable=False),
        sa.Column("provenance_id", sa.String(36)),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("lifecycle_status", sa.String(32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "concepts",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(256), nullable=False),
        sa.Column("original_language_term", sa.String(256)),
        sa.Column("transliteration", sa.String(256)),
        sa.Column("definition", sa.Text(), nullable=False),
        sa.Column("aliases", sa.JSON()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "langgraph_checkpoints",
        sa.Column("thread_id", sa.String(128), primary_key=True),
        sa.Column("checkpoint_id", sa.String(128), primary_key=True),
        sa.Column("parent_checkpoint_id", sa.String(128)),
        sa.Column("state_payload", sa.JSON(), nullable=False),
        sa.Column("metadata_payload", sa.JSON()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "research_questions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("main_question", sa.Text(), nullable=False),
        sa.Column("subquestions", sa.JSON()),
        sa.Column("scope", sa.Text()),
        sa.Column("domain", sa.String(128)),
        sa.Column("constraints", sa.JSON()),
        sa.Column("user_position", sa.Text()),
        sa.Column("open_questions", sa.JSON()),
        sa.Column("research_status", sa.String(32), nullable=False),
        sa.Column("research_history", sa.JSON()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "research_runs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("query", sa.Text(), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("error_message", sa.Text()),
        sa.Column("output_references", sa.JSON()),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
    )
    op.create_table(
        "sources",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("title", sa.String(512), nullable=False),
        sa.Column("author", sa.String(256)),
        sa.Column("historical_era", sa.String(128)),
        sa.Column("original_language", sa.String(64)),
        sa.Column("source_type", source_type, nullable=False),
        sa.Column("reference_url", sa.String(1024)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "users",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("username", sa.String(128), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "assumptions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("argument_id", sa.String(36), sa.ForeignKey("arguments.id"), nullable=False),
        sa.Column("statement", sa.Text(), nullable=False),
    )
    op.create_table(
        "cognitive_observations",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("observation_type", sa.String(64), nullable=False),
        sa.Column("observation_detail", sa.Text(), nullable=False),
        sa.Column("evidence_reference", sa.Text(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("originating_interaction_id", sa.String(36), nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "concept_relationships",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("source_concept_id", sa.String(36), sa.ForeignKey("concepts.id"), nullable=False),
        sa.Column("target_concept_id", sa.String(36), sa.ForeignKey("concepts.id"), nullable=False),
        sa.Column("relationship_type", sa.String(64), nullable=False),
    )
    op.create_table(
        "conversations",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("title", sa.String(256)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "documents",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("source_id", sa.String(36), sa.ForeignKey("sources.id"), nullable=False),
        sa.Column("checksum_sha256", sa.String(64), nullable=False),
        sa.Column("mime_type", sa.String(128), nullable=False),
        sa.Column("total_pages", sa.Integer()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "epistemic_positions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("claim_statement", sa.Text(), nullable=False),
        sa.Column("position", sa.Text(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("supporting_evidence_payload", sa.JSON()),
        sa.Column("counterarguments_payload", sa.JSON()),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "objections",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("argument_id", sa.String(36), sa.ForeignKey("arguments.id"), nullable=False),
        sa.Column("objection_statement", sa.Text(), nullable=False),
        sa.Column("reply_statement", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "passages",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("document_id", sa.String(36), sa.ForeignKey("documents.id"), nullable=False),
        sa.Column("page_number", sa.Integer()),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("ocr_confidence", sa.Float()),
        sa.Column("extraction_uncertainty", sa.Boolean(), nullable=False),
        sa.Column("language", sa.String(16), nullable=False),
        sa.Column("embedding_model", sa.String(128)),
        sa.Column("embedding", Vector(384)),
    )
    op.create_table(
        "premises",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("argument_id", sa.String(36), sa.ForeignKey("arguments.id"), nullable=False),
        sa.Column("statement", sa.Text(), nullable=False),
        sa.Column("is_supported", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "research_steps",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("run_id", sa.String(36), sa.ForeignKey("research_runs.id"), nullable=False),
        sa.Column("step_name", sa.String(128), nullable=False),
        sa.Column("step_type", sa.String(64), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("payload", sa.JSON()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "source_criticisms",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("source_id", sa.String(36), sa.ForeignKey("sources.id"), nullable=False),
        sa.Column("finding", sa.Text(), nullable=False),
        sa.Column("basis", sa.Text(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("status", evidence_status, nullable=False),
        sa.Column("supporting_evidence_payload", sa.JSON()),
        sa.Column("contradicting_evidence_payload", sa.JSON()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "source_relationships",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("source_id", sa.String(36), sa.ForeignKey("sources.id"), nullable=False),
        sa.Column("target_id", sa.String(36), sa.ForeignKey("sources.id"), nullable=False),
        sa.Column("relationship_type", source_relationship_type, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("source_id", "target_id", "relationship_type", name="uix_source_target_rel"),
    )
    op.create_table(
        "epistemic_history",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("position_id", sa.String(36), sa.ForeignKey("epistemic_positions.id"), nullable=False),
        sa.Column("previous_status", sa.String(32), nullable=False),
        sa.Column("new_status", sa.String(32), nullable=False),
        sa.Column("change_reason", sa.Text()),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "messages",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("conversation_id", sa.String(36), sa.ForeignKey("conversations.id"), nullable=False),
        sa.Column("role", sa.String(32), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("research_run_id", sa.String(36), sa.ForeignKey("research_runs.id")),
        sa.Column("citations_payload", sa.JSON()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "evidence_links",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("claim_id", sa.String(36), sa.ForeignKey("claims.id")),
        sa.Column("premise_id", sa.String(36), sa.ForeignKey("premises.id")),
        sa.Column("passage_id", sa.String(36), sa.ForeignKey("passages.id"), nullable=False),
        sa.Column("relation_type", relation_type, nullable=False),
        sa.Column("confidence_weight", sa.Float(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_index("ix_users_username", "users", ["username"], unique=True)
    op.create_index("ix_documents_checksum_sha256", "documents", ["checksum_sha256"], unique=True)
    op.create_index("ix_concepts_name", "concepts", ["name"], unique=True)
    op.create_index("ix_source_relationships_source_id", "source_relationships", ["source_id"])
    op.create_index("ix_source_relationships_target_id", "source_relationships", ["target_id"])


def downgrade() -> None:
    for table_name in (
        "evidence_links", "messages", "epistemic_history", "source_relationships",
        "source_criticisms", "research_steps", "premises", "passages", "objections",
        "epistemic_positions", "documents", "conversations", "concept_relationships",
        "cognitive_observations", "assumptions", "users", "sources", "research_runs",
        "research_questions", "langgraph_checkpoints", "concepts", "claims", "arguments",
    ):
        # Keep local recovery idempotent when an isolated test database has
        # removed objects while retaining the Alembic version row.
        op.execute(sa.text(f'DROP TABLE IF EXISTS "{table_name}" CASCADE'))

    for enum_name in ("evidencestatus", "relationtype", "claimtype", "sourcerelationshiptype", "sourcetype"):
        op.execute(sa.text(f"DROP TYPE IF EXISTS {enum_name}"))
