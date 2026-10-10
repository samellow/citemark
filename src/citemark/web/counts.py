"""Daily counts (onboarding plan 7, Q4): measured on this server only, per day, never per person.

- **What's counted:** demo page views, audit-button clicks, suggested-question taps and published
  report opens, each split by the pitch variant a proposal link carried (`?v=accuracy` or
  `?v=build`). Any other `v` counts as none, so a link can't add rows of its own.
- **Not counted:** link previews, crawlers and scripts, told apart by their user agent. A visitor
  is never identified: no cookie, no address, no order of events.
"""

from __future__ import annotations

import datetime as dt
import re

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from citemark.db.models import COUNTED_EVENTS, VARIANTS, DailyCount

# Known non-people: crawlers, link previews (Upwork's messages, Slack and others) and HTTP libraries
NOT_PEOPLE = re.compile(
    r"bot\b|bot/|crawl|spider|slurp|preview|facebookexternalhit|embedly|whatsapp|telegram|discord|slack|"
    r"headless|lighthouse|curl/|wget/|python-|httpx|go-http-client|okhttp|java/|axios|node-fetch|monitor",
    re.IGNORECASE,
)


def variant(value: str | None) -> str:
    return value if value in VARIANTS else ""


def is_person(user_agent: str | None) -> bool:
    """Whether a request looks like a person's browser. A missing user agent is a script's."""
    return bool(user_agent) and NOT_PEOPLE.search(user_agent or "") is None


async def count(session: AsyncSession, event: str, pitch: str, *, day: dt.date) -> None:
    if event not in COUNTED_EVENTS:
        raise ValueError(f"{event} isn't a counted event. The counted ones are {', '.join(COUNTED_EVENTS)}.")
    await session.execute(
        insert(DailyCount)
        .values(day=day, event=event, variant=variant(pitch), count=1)
        .on_conflict_do_update(
            index_elements=[DailyCount.day, DailyCount.event, DailyCount.variant],
            set_={"count": DailyCount.count + 1},
        )
    )
