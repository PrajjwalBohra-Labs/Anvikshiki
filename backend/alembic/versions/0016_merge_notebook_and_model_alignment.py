"""Merge the notebook and main schema migration branches."""

from collections.abc import Sequence

revision: str = "0016_merge_schema_heads"
down_revision: tuple[str, str] = ("0006_notebook_foundation", "0015_model_alignment")
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Merge-only revision; both parent branches already apply their changes."""


def downgrade() -> None:
    """Merge-only revision; downgrade is handled by the parent branches."""
