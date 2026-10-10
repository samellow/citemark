"""The ask box's limits (PRD 8.2, 5.6, 5.11): 10 questions an hour per visitor, and a daily spend cap.

- **A visitor is a salted hash of their address,** kept in memory only, never stored or logged.
  The salt is drawn again each day (UTC), which also empties the table.
- **The address** comes from the header the host's proxy sets (`CLIENT_IP_HEADER`:
  CF-Connecting-IP on Render), since the connection itself comes from the proxy. Without that, every
  visitor would share one limit. X-Forwarded-For is never read: on Render a visitor can put any
  address at its start.
- **The hour slides:** an eleventh question in any hour is refused, with the minutes until the
  oldest of the ten drops out.
- **An IPv6 visitor is their /64,** the block one connection is usually given, so changing
  address within it doesn't give a new hour.
- **The spend cap** is today's spend (UTC) on every answer, against the `daily_spend_cap_usd`
  setting: $1 unless set. The app answers at most four questions at once and checks the cap again
  when each one's turn comes, so a day can go over by at most the answers under way: cents.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import ipaddress
import math
import secrets
import time
from collections import deque
from collections.abc import Callable, Mapping
from decimal import Decimal, InvalidOperation

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from citemark.db.models import Message, Setting

QUESTIONS_AN_HOUR = 10
HOUR = 3600.0
VISITORS = 100_000  # the most kept at once; past it, the longest-idle is forgotten
SPEND_CAP = "daily_spend_cap_usd"
DEFAULT_SPEND_CAP = Decimal("1.00")  # chosen with you in T16: at most about $30 a month


def utc_today() -> dt.date:
    return dt.datetime.now(dt.UTC).date()


class RateLimiter:
    """Counts each visitor's questions over the last hour, in memory."""

    def __init__(
        self,
        limit: int = QUESTIONS_AN_HOUR,
        window: float = HOUR,
        *,
        clock: Callable[[], float] = time.monotonic,
        today: Callable[[], dt.date] = utc_today,
        visitors: int = VISITORS,
    ) -> None:
        self.limit, self.window, self.visitors = limit, window, visitors
        self._clock, self._today = clock, today
        self._day: dt.date | None = None
        self._salt = b""
        self._asked: dict[bytes, deque[float]] = {}

    def _key(self, address: str) -> bytes:
        day = self._today()
        if day != self._day:  # a new day: a new salt, and yesterday's hashes are gone
            self._day, self._salt, self._asked = day, secrets.token_bytes(16), {}
        return hashlib.blake2b(address.encode(), key=self._salt, digest_size=16).digest()

    def ask(self, address: str) -> int | None:
        """Count a question from `address`: None when it may be asked, or else the whole minutes
        until it may, at least 1."""
        key, now = self._key(address), self._clock()
        asked = self._asked.pop(key, None) or deque()
        while asked and asked[0] <= now - self.window:
            asked.popleft()
        self._asked[key] = asked  # moved to the end: the most recently seen
        if len(asked) >= self.limit:
            return max(1, math.ceil((asked[0] + self.window - now) / 60))
        asked.append(now)
        while len(self._asked) > self.visitors:
            del self._asked[next(iter(self._asked))]
        return None

    def remembered(self) -> int:
        """How many visitors it holds, for its tests: an empty one is still a limiter."""
        return len(self._asked)


def _visitor(value: str) -> str | None:
    """An address as one visitor: an IPv4 address, or an IPv6 address's /64."""
    try:
        address = ipaddress.ip_address(value.strip())
    except ValueError:
        return None
    if isinstance(address, ipaddress.IPv6Address):
        if address.ipv4_mapped is not None:
            return str(address.ipv4_mapped)
        return str(ipaddress.ip_network(f"{address}/64", strict=False))
    return str(address)


def client_address(headers: Mapping[str, str], peer: str | None, header: str | None) -> str:
    """The visitor: from the proxy's header when one is set and holds an address, or else the
    connection's own."""
    if header and (visitor := _visitor(headers.get(header, ""))):
        return visitor
    # Missing or not an address: the request didn't come through the proxy as expected
    return (_visitor(peer) if peer else None) or peer or "unknown"


def _day_start(day: dt.date) -> dt.datetime:
    return dt.datetime.combine(day, dt.time(), tzinfo=dt.UTC)


async def spend_cap(session: AsyncSession) -> Decimal:
    stored = await session.get(Setting, SPEND_CAP)
    if stored is None:
        return DEFAULT_SPEND_CAP
    try:
        return Decimal(str(stored.value))
    except InvalidOperation as exc:
        raise ValueError(f"The {SPEND_CAP} setting holds {stored.value!r}, which isn't an amount.") from exc


async def set_spend_cap(session: AsyncSession, amount: Decimal, *, by: str) -> None:
    if amount < 0:
        raise ValueError("A spend cap can't be negative.")
    value = str(amount.quantize(Decimal("0.01")))
    await session.execute(
        insert(Setting)
        .values(key=SPEND_CAP, value=value, updated_by=by)
        .on_conflict_do_update(
            index_elements=[Setting.key], set_={"value": value, "updated_by": by, "updated_at": func.now()}
        )
    )


async def spent_today(session: AsyncSession, today: dt.date) -> Decimal:
    """What every answer since midnight UTC cost, the follow-up rewrites and searches included."""
    start = _day_start(today)
    total = await session.scalar(
        select(func.coalesce(func.sum(Message.cost_usd), 0)).where(
            Message.created_at >= start, Message.created_at < start + dt.timedelta(days=1)
        )
    )
    return Decimal(total)


async def over_spend_cap(session: AsyncSession, today: dt.date) -> bool:
    return await spent_today(session, today) >= await spend_cap(session)
