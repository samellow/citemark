"""Prices for the models and services the bot calls (PRD 5.12), in USD per million tokens.

Read from Anthropic's and Voyage's pricing pages on 2026-10-09. Cache writes are the 5-minute
kind, which is what the bot uses. Haiku 5.5 costs more for prompts over 100,000 tokens, counting
cached tokens too, so it has two rows. A price change is a new row with a later date, in a new
migration, so a report keeps the prices of the day its calls were made. Recheck them before the
decision runs (implementation plan T8).

Revision ID: 0003
Revises: 0002
Create Date: 2026-10-09
"""

import datetime as dt
from collections.abc import Sequence
from decimal import Decimal

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: str | Sequence[str] | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

CHECKED = dt.date(2026, 10, 9)
# model, prompts of at least this many tokens, input, output, cache read, cache write
PRICES = [
    ("claude-haiku-4-5", 0, "1.00", "5.00", "0.10", "1.25"),
    ("claude-haiku-5-5", 0, "0.10", "0.50", "0.01", "0.125"),
    ("claude-haiku-5-5", 100_001, "0.50", "2.50", "0.05", "0.625"),
    ("claude-sonnet-5-5", 0, "2.00", "10.00", "0.10", "2.50"),
    ("claude-opus-5-5", 0, "4.00", "20.00", "0.20", "5.00"),
    ("voyage-4", 0, "0.06", "0", "0", "0"),
    ("rerank-3", 0, "0.05", "0", "0", "0"),
]


def upgrade() -> None:
    insert = sa.text(
        "INSERT INTO price_table (model, min_prompt_tokens, input_per_mtok, output_per_mtok,"
        " cache_read_per_mtok, cache_write_per_mtok, effective_from)"
        " VALUES (:model, :min_prompt_tokens, :input, :output, :cache_read, :cache_write, :effective_from)"
    )
    for model, min_prompt_tokens, *rates in PRICES:
        given, made, read, write = (Decimal(rate) for rate in rates)
        op.execute(
            insert.bindparams(
                model=model,
                min_prompt_tokens=min_prompt_tokens,
                input=given,
                output=made,
                cache_read=read,
                cache_write=write,
                effective_from=CHECKED,
            )
        )


def downgrade() -> None:
    op.execute(sa.text("DELETE FROM price_table WHERE effective_from = :checked").bindparams(checked=CHECKED))
