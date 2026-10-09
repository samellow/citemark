"""The abuse set's planted article (QA plan 4.3, T12).

A question that plants instructions in an article names the article's file, and keeps the content
hash the article is indexed under, worked out from the frozen file when the set is first run.
Every run checks the database against it as it starts or resumes, so the attack is the frozen
one, and an accuracy run never meets it. A result is scored as tested only when the article was
among the passages the bot was given. The abuse kinds become a fixed list, like the question
types.

Revision ID: 0007
Revises: 0006
Create Date: 2026-10-09
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0007"
down_revision: str | Sequence[str] | None = "0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

ABUSE_KINDS = (
    "invents_policy",
    "planted_instruction",
    "off_topic",
    "asks_for_instructions",
    "personal_data",
    "other_language",
    "odd_input",
)


def upgrade() -> None:
    op.add_column("test_question", sa.Column("planted_article", sa.Text(), nullable=True))
    op.add_column("test_question", sa.Column("planted_hash", sa.Text(), nullable=True))
    allowed = ", ".join(f"'{kind}'" for kind in ABUSE_KINDS)
    op.create_check_constraint(op.f("ck_test_question_abuse_kind"), "test_question", f"abuse_kind IN ({allowed})")
    op.create_check_constraint(
        op.f("ck_test_question_planted_article"),
        "test_question",
        "abuse_kind = 'planted_instruction' OR planted_article IS NULL",
    )
    op.create_check_constraint(
        op.f("ck_test_question_planted_hash"),
        "test_question",
        "(planted_article IS NULL) = (planted_hash IS NULL)",
    )


def downgrade() -> None:
    op.drop_constraint(op.f("ck_test_question_planted_hash"), "test_question", type_="check")
    op.drop_constraint(op.f("ck_test_question_planted_article"), "test_question", type_="check")
    op.drop_constraint(op.f("ck_test_question_abuse_kind"), "test_question", type_="check")
    op.drop_column("test_question", "planted_hash")
    op.drop_column("test_question", "planted_article")
