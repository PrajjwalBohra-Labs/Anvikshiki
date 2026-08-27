"""Allow external identities on research questions.

Revision ID: 0003_relax_question_identity_fk
Revises: 0002_public_research_contracts
"""

from collections.abc import Sequence

from alembic import op


revision: str = "0003_relax_question_identity_fk"
down_revision: str | None = "0002_public_research_contracts"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint(
        "fk_research_questions_user_id_users",
        "research_questions",
        type_="foreignkey",
    )
    op.create_unique_constraint(
        "uix_research_step_run_sequence",
        "research_steps",
        ["run_id", "event_sequence"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uix_research_step_run_sequence",
        "research_steps",
        type_="unique",
    )
    op.create_foreign_key(
        "fk_research_questions_user_id_users",
        "research_questions",
        "users",
        ["user_id"],
        ["id"],
    )
