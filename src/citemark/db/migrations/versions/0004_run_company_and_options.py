"""What a test run needs to be resumed and re-scored (T9).

- `test_run.company`: the product name the answer prompt is filled with. It changes the
  prompt, so it's recorded like every other setting that could change a score (PRD 4.3).
- `test_result.clarify_options`: the options the bot offered when it asked which meaning was
  meant, so re-scoring can tell whether the expected one was among them.

Revision ID: 0004
Revises: 0003
Create Date: 2026-10-09
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0004"
down_revision: str | Sequence[str] | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("test_run", sa.Column("company", sa.Text(), server_default="", nullable=False))
    op.alter_column("test_run", "company", server_default=None)  # a new run always names it
    op.add_column("test_result", sa.Column("clarify_options", postgresql.JSONB(none_as_null=True), nullable=True))


def downgrade() -> None:
    op.drop_column("test_result", "clarify_options")
    op.drop_column("test_run", "company")
