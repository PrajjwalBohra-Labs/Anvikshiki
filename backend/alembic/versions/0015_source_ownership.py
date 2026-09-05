"""Associate sources with local research identities."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "0015_source_ownership"
down_revision: str | None = "0014_merge_heads"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("sources", sa.Column("user_id", sa.String(length=36), nullable=True))
    op.create_index("ix_sources_user_id", "sources", ["user_id"])
    op.create_foreign_key(
        "fk_sources_user_id_users",
        "sources",
        "users",
        ["user_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("fk_sources_user_id_users", "sources", type_="foreignkey")
    op.drop_index("ix_sources_user_id", table_name="sources")
    op.drop_column("sources", "user_id")
