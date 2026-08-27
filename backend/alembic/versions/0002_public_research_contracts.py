"""Add public research run ownership, results, and replay metadata.

Revision ID: 0002_public_research_contracts
Revises: 0001_initial_schema
Create Date: 2026-08-27
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0002_public_research_contracts"
down_revision: Union[str, Sequence[str], None] = "0001_initial_schema"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("research_questions", sa.Column("user_id", sa.String(36), nullable=True))
    op.create_index("ix_research_questions_user_id", "research_questions", ["user_id"])
    op.create_foreign_key(
        "fk_research_questions_user_id_users",
        "research_questions",
        "users",
        ["user_id"],
        ["id"],
    )

    op.add_column("research_runs", sa.Column("user_id", sa.String(36), nullable=True))
    op.add_column("research_runs", sa.Column("research_question_id", sa.String(36), nullable=True))
    op.add_column("research_runs", sa.Column("thread_id", sa.String(128), nullable=True))
    op.add_column("research_runs", sa.Column("domain", sa.String(128), nullable=True))
    op.add_column("research_runs", sa.Column("depth", sa.String(32), nullable=True))
    op.create_index("ix_research_runs_user_id", "research_runs", ["user_id"])
    op.create_index("ix_research_runs_research_question_id", "research_runs", ["research_question_id"])
    op.create_index("ix_research_runs_thread_id", "research_runs", ["thread_id"])
    op.create_foreign_key(
        "fk_research_runs_research_question_id_questions",
        "research_runs",
        "research_questions",
        ["research_question_id"],
        ["id"],
    )

    op.add_column("claims", sa.Column("research_run_id", sa.String(36), nullable=True))
    op.create_index("ix_claims_research_run_id", "claims", ["research_run_id"])
    op.create_foreign_key(
        "fk_claims_research_run_id_runs",
        "claims",
        "research_runs",
        ["research_run_id"],
        ["id"],
    )

    op.add_column("documents", sa.Column("original_filename", sa.String(512), nullable=True))
    op.add_column("documents", sa.Column("storage_path", sa.String(1024), nullable=True))

    op.add_column("research_steps", sa.Column("event_id", sa.String(192), nullable=True))
    op.add_column("research_steps", sa.Column("event_sequence", sa.Integer(), nullable=True))
    op.create_index("ix_research_steps_event_id", "research_steps", ["event_id"])
    op.create_index("ix_research_steps_event_sequence", "research_steps", ["event_sequence"])


def downgrade() -> None:
    op.drop_index("ix_research_steps_event_sequence", table_name="research_steps")
    op.drop_index("ix_research_steps_event_id", table_name="research_steps")
    op.drop_column("research_steps", "event_sequence")
    op.drop_column("research_steps", "event_id")

    op.drop_column("documents", "storage_path")
    op.drop_column("documents", "original_filename")

    op.drop_constraint("fk_claims_research_run_id_runs", "claims", type_="foreignkey")
    op.drop_index("ix_claims_research_run_id", table_name="claims")
    op.drop_column("claims", "research_run_id")

    op.drop_constraint("fk_research_runs_research_question_id_questions", "research_runs", type_="foreignkey")
    op.drop_index("ix_research_runs_thread_id", table_name="research_runs")
    op.drop_index("ix_research_runs_research_question_id", table_name="research_runs")
    op.drop_index("ix_research_runs_user_id", table_name="research_runs")
    for column in ("depth", "domain", "thread_id", "research_question_id", "user_id"):
        op.drop_column("research_runs", column)

    op.drop_constraint("fk_research_questions_user_id_users", "research_questions", type_="foreignkey")
    op.drop_index("ix_research_questions_user_id", table_name="research_questions")
    op.drop_column("research_questions", "user_id")
