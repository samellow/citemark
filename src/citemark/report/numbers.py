"""The report's numbers (content spec 2.3): rounded against the bot, with states from exact values.

- **Round against the bot** (content spec Q2): a percent where higher is better is rounded down,
  and one where lower is better is rounded up. Money is rounded up.
- **States come from the exact values,** before any rounding, so a shown number and its state can
  never disagree in the bot's favor.
- **Warn** is a target missed by less than 5 points (design system 3.1: "within 5 points of the
  threshold"). Missed by 5 points or more is Fail, so the boundary also falls against the bot.
  The prototype's example is 37 of 40 against a target of 95%: Warn.
"""

from __future__ import annotations

import datetime as dt
from decimal import ROUND_CEILING, Decimal
from fractions import Fraction

WARN_POINTS = 5
MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")
FINGERPRINT = 8  # characters of a hash shown


def percent_down(passed: int, total: int) -> int:
    """A score where higher is better: 89.96% shows as 89%."""
    return passed * 100 // total


def percent_up(count: int, total: int) -> int:
    """A rate where lower is better: 5.01% shows as 6%."""
    return -(-count * 100 // total)


def state(count: int, total: int, target: int, *, lower_is_better: bool) -> str:
    """Pass, warn or fail, from the exact share against a whole-percent target."""
    exact = Fraction(count * 100, total)
    missed_by = exact - target if lower_is_better else target - exact
    if missed_by <= 0:
        return "pass"
    return "warn" if missed_by < WARN_POINTS else "fail"


def money(usd: Decimal) -> str:
    """Dollars without the sign: under $1 to 3 significant figures, else whole dollars, both
    rounded up. A cost that rounds up to $1 is shown as whole dollars."""
    if usd < 0:
        raise ValueError(f"A cost can't be negative, and {usd} is.")
    if usd == 0:
        return "0"
    if usd < 1:
        places = Decimal(1).scaleb(usd.adjusted() - 2)  # the third significant figure
        rounded = usd.quantize(places, rounding=ROUND_CEILING)
        if rounded < 1:
            return f"{rounded:f}"
    return f"{usd.quantize(Decimal(1), rounding=ROUND_CEILING):,f}"


def date(day: dt.date) -> str:
    """Oct 5, 2026, the same in every locale."""
    return f"{MONTHS[day.month - 1]} {day.day}, {day.year}"


def fingerprint(digest: str) -> str:
    return digest[:FINGERPRINT]
