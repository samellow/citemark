"""The job worker: runs inside the app process (PRD Q1), one job at a time.

It also queues the daily jobs, checking every 10 minutes whether one is due (PRD 3). The
monthly re-test and the nightly re-index join that schedule in Phase 3.
"""

from __future__ import annotations

import asyncio
import contextlib
import uuid
from collections.abc import Awaitable, Callable, Iterable, Mapping
from dataclasses import dataclass, field
from typing import Any

import structlog
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine, AsyncSession, async_sessionmaker

from citemark.db.session import make_engine, make_sessionmaker
from citemark.jobs.queue import JobCancelled, claim, ensure_daily, finish, report_progress

log = structlog.get_logger()

DAILY = ("purge",)


@dataclass
class JobContext:
    """What a handler gets: its job, sessions for its own work, and a way to save progress."""

    id: uuid.UUID
    type: str
    payload: dict[str, Any]
    attempt: int  # 1 on the first run; more after a worker stopped mid-job
    resume_from: int  # the progress an earlier attempt saved
    sessions: async_sessionmaker[AsyncSession]
    _connection: AsyncConnection
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock)

    async def progress(
        self, done: int, total: int | None = None, label: str | None = None, *, session: AsyncSession | None = None
    ) -> None:
        """Save real counts, such as 120 of 257 articles. `label` names what's counted.

        Pass the session doing the work to save the work and the count in one transaction,
        so a step that's saved is never redone after a crash. Raises `JobCancelled` if the
        job was cancelled."""
        if session is not None:
            await report_progress(session, self.id, done, total, label)
            return
        async with self._lock, self._connection.begin():
            await report_progress(self._connection, self.id, done, total, label)


Handler = Callable[[JobContext], Awaitable[None]]


def handlers() -> dict[str, Handler]:
    """The job types this app runs. Imported here, so modules can queue jobs without a cycle."""
    from citemark.ingest.pipeline import ingest
    from citemark.jobs.purge import purge

    return {"ingest": ingest, "purge": purge}


class Worker:
    def __init__(
        self,
        engine: AsyncEngine,
        handlers: Mapping[str, Handler],
        *,
        daily: Iterable[str] = (),
        poll_seconds: float = 2.0,
        schedule_seconds: float = 600.0,
    ) -> None:
        self.engine = engine
        self.handlers = dict(handlers)
        self.daily = tuple(daily)
        self.poll_seconds = poll_seconds
        self.schedule_seconds = schedule_seconds
        self.sessions = make_sessionmaker(engine)

    async def run(self, stop: asyncio.Event) -> None:
        """Run jobs until `stop` is set. A database error is logged, and the worker tries again."""
        loop = asyncio.get_running_loop()
        next_schedule = loop.time()
        while not stop.is_set():
            try:
                if self.daily and loop.time() >= next_schedule:
                    await self.schedule()
                    next_schedule = loop.time() + self.schedule_seconds
                if await self.run_once():
                    continue
            except Exception:
                log.exception("job_worker_error")
            with contextlib.suppress(TimeoutError):
                await asyncio.wait_for(stop.wait(), self.poll_seconds)

    async def run_until_idle(self) -> None:
        while await self.run_once():
            pass

    async def schedule(self) -> None:
        async with self.sessions.begin() as session:
            for type in self.daily:
                if await ensure_daily(session, type):
                    log.info("job_queued", job_type=type, reason="daily")

    async def run_once(self) -> bool:
        """Run the oldest waiting job, if there is one. Returns whether a job ran."""
        async with self.engine.connect() as connection:
            try:
                job = await claim(connection, self.handlers)
                if job is None:
                    return False
                job_log = log.bind(job_id=str(job.id), job_type=job.type, attempt=job.attempt)
                job_log.info("job_started")
                context = JobContext(
                    id=job.id,
                    type=job.type,
                    payload=job.payload,
                    attempt=job.attempt,
                    resume_from=job.progress_done,
                    sessions=self.sessions,
                    _connection=connection,
                )
                try:
                    await self.handlers[job.type](context)
                except JobCancelled:
                    status, error = None, None
                    job_log.info("job_cancelled")
                except Exception as exc:
                    status, error = "failed", f"{type(exc).__name__}: {exc}"
                    job_log.exception("job_failed")
                else:
                    status, error = "done", None
                    job_log.info("job_done")
                await finish(connection, job.id, status, error)
            except BaseException:
                # Drop the connection, and any job lock with it, so the next worker resumes the job
                await connection.invalidate()
                raise
        return True


async def run_worker(*, until_idle: bool = False) -> None:
    """The worker for `citemark jobs work`, with the app's own job types."""
    engine = make_engine()
    worker = Worker(engine, handlers(), daily=DAILY)
    try:
        if until_idle:
            await worker.schedule()
            await worker.run_until_idle()
        else:
            await worker.run(asyncio.Event())
    finally:
        await engine.dispose()
