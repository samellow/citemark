"""Where an answer's source markers go (T14).

A result kept the answer as plain text and its citations, but not which stretch of the answer each
marker follows, so the report couldn't show the ¹ beside the words it supports (PRD 8.1). A result
now keeps the answer's segments, each with its markers, and the gap phrase of a partial answer.
Results saved before this have neither, and a report refuses them rather than guess.

Revision ID: 0008
Revises: 0007
Create Date: 2026-10-09
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0008"
down_revision: str | Sequence[str] | None = "0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("test_result", sa.Column("segments", postgresql.JSONB(), nullable=True))
    op.add_column("test_result", sa.Column("gap_text", sa.Text(), nullable=True))
    op.create_check_constraint(
        op.f("ck_test_result_segments"), "test_result", "kind IN ('answer', 'partial') OR segments IS NULL"
    )
    op.create_check_constraint(op.f("ck_test_result_gap_text"), "test_result", "kind = 'partial' OR gap_text IS NULL")


def downgrade() -> None:
    op.drop_constraint(op.f("ck_test_result_gap_text"), "test_result", type_="check")
    op.drop_constraint(op.f("ck_test_result_segments"), "test_result", type_="check")
    op.drop_column("test_result", "gap_text")
    op.drop_column("test_result", "segments")
