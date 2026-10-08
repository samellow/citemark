"""The job queue (PRD 3 and 5.10): rows in `job`, claimed with `FOR UPDATE SKIP LOCKED`.

A worker holds a session-level advisory lock on each job it runs, on a connection it keeps
for as long as the job runs. If the worker dies, Postgres closes that connection and drops
the lock with it, so the next worker finds a `running` job that nobody holds and takes it
over. Handlers resume from the progress they saved, which is how a killed job still finishes
exactly once (QA promise 16).
"""

from __future__ import annotations

import datetime as dt
import uuid
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

from sqlalchemy import func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncSession

from citemark.db.models import Job

MAX_ATTEMPTS = 3
CANDIDATES = 10  # jobs looked at per claim, since running ones held by live workers are passed over


class JobCancelled(Exception):
    """Someone cancelled the job while it ran. Raised at its next progress report."""


@dataclass(frozen=True)
class Claimed:
    id: uuid.UUID
    type: str
    payload: dict[str, Any]
    attempt: int
    progress_done: int  # saved by an earlier attempt, so the handler can resume from there


def _lock_key(job_id: uuid.UUID):
    return func.hashtextextended(str(job_id), 0)


async def enqueue(session: AsyncSession, type: str, payload: dict[str, Any] | None = None) -> uuid.UUID:
    job = Job(type=type, payload=payload or {})
    session.add(job)
    await session.flush()
    return job.id


async def claim(connection: AsyncConnection, types: Iterable[str]) -> Claimed | None:
    """Take the oldest job of these types that nobody is running, and hold its lock on
    `connection` until `finish()`. A job that has used up its attempts is failed instead.

    If this raises after taking a lock, the caller must close or invalidate the connection,
    which drops the lock."""
    candidates = (
        select(Job.id, Job.attempts)
        .where(Job.type.in_(list(types)), Job.status.in_(("queued", "running")))
        .order_by(Job.created_at, Job.id)
        .limit(CANDIDATES)
        .with_for_update(skip_locked=True)
    )
    async with connection.begin():
        for job_id, attempts in (await connection.execute(candidates)).all():
            if not await connection.scalar(select(func.pg_try_advisory_lock(_lock_key(job_id)))):
                continue  # a live worker is running it
            if attempts >= MAX_ATTEMPTS:
                # Each attempt ended with the worker stopping mid-job, so another would too
                stop = {
                    "status": "failed",
                    "error": f"Stopped after {MAX_ATTEMPTS} attempts.",
                    "finished_at": func.now(),
                }
                await connection.execute(update(Job).where(Job.id == job_id).values(**stop))
                await connection.execute(select(func.pg_advisory_unlock(_lock_key(job_id))))
                continue
            started = (
                update(Job)
                .where(Job.id == job_id)
                .values(status="running", attempts=Job.attempts + 1, locked_at=func.now())
                .returning(Job.id, Job.type, Job.payload, Job.attempts, Job.progress_done)
            )
            return Claimed(*(await connection.execute(started)).one())
    return None


async def report_progress(
    executor: AsyncConnection | AsyncSession, job_id: uuid.UUID, done: int, total: int | None, label: str | None
) -> None:
    """Save real counts. Raises `JobCancelled` if the job was cancelled meanwhile."""
    values: dict[str, Any] = {"progress_done": done}
    if total is not None:
        values["progress_total"] = total
    if label is not None:
        values["progress_label"] = label
    saved = update(Job).where(Job.id == job_id, Job.status == "running").values(**values).returning(Job.id)
    if await executor.scalar(saved) is None:
        raise JobCancelled(job_id)


async def finish(connection: AsyncConnection, job_id: uuid.UUID, status: str | None, error: str | None = None) -> None:
    """Record how the job ended (`None` leaves a cancelled job as it is) and drop its lock."""
    async with connection.begin():
        if status is not None:
            ended = {"status": status, "error": error, "finished_at": func.now(), "locked_at": None}
            await connection.execute(update(Job).where(Job.id == job_id, Job.status == "running").values(**ended))
        await connection.execute(select(func.pg_advisory_unlock(_lock_key(job_id))))


async def cancel(session: AsyncSession, job_id: uuid.UUID) -> bool:
    """Cancel a waiting or running job. A running one stops at its next progress report."""
    cancelled = (
        update(Job)
        .where(Job.id == job_id, Job.status.in_(("queued", "running")))
        .values(status="cancelled", finished_at=func.now())
        .returning(Job.id)
    )
    return await session.scalar(cancelled) is not None


async def ensure_daily(session: AsyncSession, type: str) -> bool:
    """Queue a job of this type unless one is waiting, running, or was queued in the last day."""
    await session.execute(select(func.pg_advisory_xact_lock(func.hashtext(f"daily:{type}"))))
    recent = or_(Job.status.in_(("queued", "running")), Job.created_at > func.now() - dt.timedelta(days=1))
    if await session.scalar(select(Job.id).where(Job.type == type, recent).limit(1)) is not None:
        return False
    await enqueue(session, type)
    return True
