"""A grade locks once grading is complete, and the database refuses to change it (PRD Q18).

When every answer on a grading sheet has your grade, the judge's verdicts are shown, so you can
see where the two of you disagreed. A grade changed after that would lean toward the judge, and
the published agreement would drift upward. On a decision run's queue, it would let a grade be
adjusted after seeing the result. `locked_at` records when the sheet was completed.

Revision ID: 0006
Revises: 0005
Create Date: 2026-10-09
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0006"
down_revision: str | Sequence[str] | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

RULES = [
    """
    CREATE FUNCTION refuse_locked_grade_change() RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN
      IF OLD.locked_at IS NOT NULL THEN
        RAISE EXCEPTION 'This grade was locked when its grading sheet was completed, so it can''t change.'
          USING ERRCODE = 'restrict_violation';
      END IF;
      IF TG_OP = 'DELETE' THEN
        RETURN OLD;
      END IF;
      RETURN NEW;
    END
    $$
    """,
    """
    CREATE TRIGGER human_grade_locked BEFORE UPDATE OR DELETE ON human_grade
    FOR EACH ROW EXECUTE FUNCTION refuse_locked_grade_change()
    """,
]


def upgrade() -> None:
    op.add_column("human_grade", sa.Column("locked_at", sa.DateTime(timezone=True), nullable=True))
    for statement in RULES:
        op.execute(statement)


def downgrade() -> None:
    op.execute("DROP TRIGGER human_grade_locked ON human_grade")
    op.execute("DROP FUNCTION refuse_locked_grade_change()")
    op.drop_column("human_grade", "locked_at")
