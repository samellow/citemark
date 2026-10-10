"""The demo page's ask box and its counts (T16).

- **An answer keeps its segments,** each with its source markers, as a test result does since
  0008, so a stored conversation shows its ¹ markers beside the words they support.
- **A reply names the question it answers.** A question and its reply are saved together once the
  answer is done, so two questions asked at once in one conversation would otherwise interleave
  by time and pair each question with the other's reply.
- **Today's spend** is summed over the day's messages, so their time is indexed.
- **Daily counts** (onboarding plan 7): page views, audit-button clicks and suggested-question
  taps, per day and per pitch variant. Counts only, never anything about a person.

Revision ID: 0009
Revises: 0008
Create Date: 2026-10-10
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0009"
down_revision: str | Sequence[str] | None = "0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("message", sa.Column("segments", postgresql.JSONB(), nullable=True))
    op.create_check_constraint(
        op.f("ck_message_segments"), "message", "kind IN ('answer', 'partial') OR segments IS NULL"
    )
    op.create_index(op.f("ix_message_created_at"), "message", ["created_at"])
    op.add_column("message", sa.Column("reply_to", sa.Uuid(), nullable=True))
    op.create_foreign_key(
        op.f("fk_message_reply_to_message"), "message", "message", ["reply_to"], ["id"], ondelete="CASCADE"
    )
    op.create_check_constraint(op.f("ck_message_reply_to"), "message", "role = 'assistant' OR reply_to IS NULL")
    op.create_table(
        "daily_count",
        sa.Column("day", sa.Date(), nullable=False),
        sa.Column("event", sa.Text(), nullable=False),
        sa.Column("variant", sa.Text(), nullable=False),
        sa.Column("count", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.CheckConstraint(
            "event IN ('page_view', 'audit_click', 'suggestion_tap', 'report_open')", name=op.f("ck_daily_count_event")
        ),
        sa.CheckConstraint("variant IN ('', 'accuracy', 'build')", name=op.f("ck_daily_count_variant")),
        sa.CheckConstraint("count >= 0", name=op.f("ck_daily_count_count")),
        sa.PrimaryKeyConstraint("day", "event", "variant", name=op.f("pk_daily_count")),
    )


def downgrade() -> None:
    op.drop_table("daily_count")
    op.drop_constraint(op.f("ck_message_reply_to"), "message", type_="check")
    op.drop_constraint(op.f("fk_message_reply_to_message"), "message", type_="foreignkey")
    op.drop_column("message", "reply_to")
    op.drop_index(op.f("ix_message_created_at"), table_name="message")
    op.drop_constraint(op.f("ck_message_segments"), "message", type_="check")
    op.drop_column("message", "segments")
