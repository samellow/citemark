"""The report's numbers (content spec 2.3; QA promise 10): counts always shown, and every rounded
number errs against the bot, with its state worked out from the exact value."""

import datetime as dt
from decimal import Decimal

import pytest

from citemark.report import numbers


def test_a_score_rounds_down_at_the_boundary():
    """89.96% shows as 89%: rounding up would show a bot that missed 90% as meeting it."""
    assert numbers.percent_down(2249, 2500) == 89
    assert numbers.percent_down(36, 40) == 90
    assert numbers.percent_down(40, 40) == 100


def test_a_rate_rounds_up_at_the_boundary():
    """A 5.01% over-decline shows as 6%."""
    assert numbers.percent_up(501, 10000) == 6
    assert numbers.percent_up(2, 40) == 5
    assert numbers.percent_up(0, 40) == 0


@pytest.mark.parametrize(
    ("count", "total", "target", "lower", "state"),
    [
        (36, 40, 90, False, "pass"),  # exactly the target
        (2249, 2500, 90, False, "warn"),  # 89.96%: missed, though it would round to 90
        (37, 40, 95, False, "warn"),  # 92.5%: the design system's example
        (34, 40, 90, False, "fail"),  # 85%: missed by exactly 5 points
        (8501, 10000, 90, False, "warn"),  # 85.01%: just within 5 points
        (2, 40, 5, True, "pass"),  # 5% against at most 5%
        (501, 10000, 5, True, "warn"),  # 5.01%, which shows as 6%
        (4, 40, 5, True, "fail"),  # 10%: over by exactly 5 points
        (399, 4000, 5, True, "warn"),  # 9.975%: just within 5 points
    ],
)
def test_the_state_comes_from_the_exact_value(count, total, target, lower, state):
    assert numbers.state(count, total, target, lower_is_better=lower) == state


@pytest.mark.parametrize(
    ("usd", "shown"),
    [
        ("0.0241", "0.0241"),
        ("0.024123", "0.0242"),  # 3 significant figures, rounded up
        ("0.00012301", "0.000124"),
        ("0.1", "0.100"),
        ("0.9996", "1"),  # rounds up to a dollar, so it's whole dollars
        ("1", "1"),
        ("1.01", "2"),  # whole dollars, rounded up
        ("24.2", "25"),
        ("1234.5", "1,235"),
        ("0", "0"),
    ],
)
def test_money_rounds_up(usd, shown):
    assert numbers.money(Decimal(usd)) == shown


def test_money_is_never_negative():
    with pytest.raises(ValueError):
        numbers.money(Decimal("-0.01"))


def test_a_date_reads_the_same_in_every_locale():
    assert numbers.date(dt.date(2026, 10, 5)) == "Oct 5, 2026"
    assert numbers.date(dt.date(2027, 1, 31)) == "Jan 31, 2027"


def test_a_fingerprint_shows_its_first_8_characters():
    assert numbers.fingerprint("2766f216e20f793dc281") == "2766f216"
