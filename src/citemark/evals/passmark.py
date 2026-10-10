"""The pass mark (PRD 4.3; QA plan 7.4): the targets agreed for a test set, with who agreed them
and when, so a report's "not pass" never looks arbitrary (design system 7, rule 4a).

A target is a whole percent for each of the five measures. Wrongly said "not covered" is lower
is better, so its target is the most it may reach. A frozen set's questions can't change, but its
pass mark can, and a report always states the one it was judged by. Until one is set, a report is
a baseline.
"""

from __future__ import annotations

import datetime as dt

from sqlalchemy.ext.asyncio import AsyncSession

from citemark.db.models import TestSet
from citemark.evals.scoring import MEASURES


class PassMarkError(Exception):
    """The pass mark can't be set as given. The message is one plain sentence."""


def parse(spec: str) -> dict[str, int]:
    """`correct_answers=90,right_source=90,…`: each of the five measures once, in whole percents."""
    targets: dict[str, int] = {}
    for part in filter(None, (piece.strip() for piece in spec.split(","))):
        name, _, value = part.partition("=")
        name = name.strip()
        if name not in MEASURES:
            raise PassMarkError(f"{name or part} isn't a measure. The five are: {', '.join(MEASURES)}.")
        if name in targets:
            raise PassMarkError(f"{name} is given twice.")
        if not (value.strip().isascii() and value.strip().isdigit()) or not 0 <= int(value) <= 100:
            raise PassMarkError(f"{name}'s target is a whole percent from 0 to 100, not {value.strip() or 'nothing'}.")
        targets[name] = int(value)
    if missing := [name for name in MEASURES if name not in targets]:
        raise PassMarkError(f"A pass mark has a target for each of the five measures. Missing: {', '.join(missing)}.")
    return targets


async def set_pass_mark(
    session: AsyncSession, test_set: TestSet, targets: dict[str, int], *, agreed_by: str, on: dt.date, today: dt.date
) -> None:
    """Record the pass mark on the set, replacing any before it."""
    if test_set.kind != "accuracy":
        raise PassMarkError(f"{test_set.name} is an abuse set, which has a gate rather than a pass mark.")
    if not agreed_by.strip():
        raise PassMarkError("Say who agreed the pass mark.")
    if on > today:
        raise PassMarkError(f"A pass mark can't have been agreed on {on.isoformat()}, which hasn't happened yet.")
    test_set.threshold = dict(targets)
    test_set.threshold_set_by = agreed_by.strip()
    test_set.threshold_set_at = dt.datetime.combine(on, dt.time(), dt.UTC)
    await session.flush()
