"""The daily `purge` job (PRD 5.11): conversations past the retention setting are deleted, and
their messages, citations and retrieval hits go with them. Handoff emails join it in Phase 2.
"""

from __future__ import annotations

import datetime as dt
from typing import TYPE_CHECKING

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from citemark.db.models import Conversation, Setting

if TYPE_CHECKING:
    from citemark.jobs.worker import JobContext

RETENTION_SETTING = "retention_days"
DEFAULT_RETENTION_DAYS = 90
BATCH = 500  # conversations per transaction, so no delete holds locks for long


class PurgeError(Exception):
    pass


async def retention_days(session: AsyncSession) -> int:
    days = await session.scalar(select(Setting.value).where(Setting.key == RETENTION_SETTING))
    if days is None:
        return DEFAULT_RETENTION_DAYS
    if isinstance(days, bool) or not isinstance(days, int) or days < 1:
        raise PurgeError(f"The {RETENTION_SETTING} setting must be a whole number of days, at least 1.")
    return days


async def delete_expired(session: AsyncSession, cutoff: dt.datetime, limit: int = BATCH) -> int:
    """Delete up to `limit` conversations started before `cutoff`, oldest first."""
    oldest = select(Conversation.id).where(Conversation.started_at < cutoff).order_by(Conversation.started_at)
    result = await session.execute(delete(Conversation).where(Conversation.id.in_(oldest.limit(limit))))
    return result.rowcount


async def purge(job: JobContext) -> None:
    async with job.sessions() as session:
        cutoff = await session.scalar(select(func.now())) - dt.timedelta(days=await retention_days(session))
        total = await session.scalar(select(func.count()).where(Conversation.started_at < cutoff))
    await job.progress(0, total, "conversations")
    done = 0
    while True:
        async with job.sessions.begin() as session:
            deleted = await delete_expired(session, cutoff)
            if not deleted:
                break
            done += deleted
            await job.progress(done, max(total, done), session=session)
