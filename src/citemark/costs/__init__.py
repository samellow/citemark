"""What calls cost (PRD 5.12), priced from the dated `price_table`.

A call is priced with the prices of its own day, so a report from March keeps March's prices.
Haiku 5.5 costs more for prompts over 100,000 tokens, counting cached tokens, so a model can
have one row per prompt-size tier. A price change adds every tier of the model at its new date.

A call with no price is an error, never a cost of zero.
"""

from __future__ import annotations

import datetime as dt
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from citemark.db.models import Price

MILLION = Decimal(1_000_000)


class PriceMissing(Exception):
    """The message is one plain sentence."""


async def price(
    session: AsyncSession,
    model: str,
    *,
    on: dt.date,
    input_tokens: int = 0,
    output_tokens: int = 0,
    cache_read_tokens: int = 0,
    cache_write_tokens: int = 0,
) -> Decimal:
    """One call's cost in USD, unrounded."""
    prompt = input_tokens + cache_read_tokens + cache_write_tokens
    listed = (
        select(func.max(Price.effective_from)).where(Price.model == model, Price.effective_from <= on).scalar_subquery()
    )
    row = await session.scalar(
        select(Price)
        .where(Price.model == model, Price.effective_from == listed, Price.min_prompt_tokens <= prompt)
        .order_by(Price.min_prompt_tokens.desc())
        .limit(1)
    )
    if row is None:
        raise PriceMissing(f"There's no price for {model} on {on.isoformat()}. Add one to the price table.")
    return (
        input_tokens * row.input_per_mtok
        + output_tokens * row.output_per_mtok
        + cache_read_tokens * row.cache_read_per_mtok
        + cache_write_tokens * row.cache_write_per_mtok
    ) / MILLION
