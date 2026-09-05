"""Merge the notebook and background-job migration branches."""

from collections.abc import Sequence


revision: str = "0014_merge_heads"
down_revision: tuple[str, str] = ("0014_background_jobs", "0006_notebook_foundation")
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
