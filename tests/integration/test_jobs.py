"""Background jobs (PRD 5.10, T4).

Most of these tests commit, since a worker only sees committed jobs. Each uses a job type of
its own, so no worker here picks up another test's jobs, and deletes what it made afterwards.
"""

import asyncio
import datetime as dt
import subprocess
import sys
import uuid
from pathlib import Path

import pytest
from sqlalchemy import delete, func, select, update
from sqlalchemy.pool import NullPool
from stepped_job import STEPS, counts, stepped

from citemark.db.models import Conversation, Job, Setting
from citemark.db.session import make_engine, make_sessionmaker
from citemark.jobs.purge import PurgeError, delete_expired, purge, retention_days
from citemark.jobs.queue import MAX_ATTEMPTS, cancel, enqueue, ensure_daily
from citemark.jobs.worker import Worker

pytestmark = pytest.mark.anyio
ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
async def engine():
    engine = make_engine(poolclass=NullPool)
    yield engine
    await engine.dispose()


@pytest.fixture
async def job_type(engine):
    name = f"test.{uuid.uuid4().hex[:12]}"
    yield name
    async with engine.begin() as connection:
        await connection.execute(delete(Job).where(Job.type == name))
        await connection.execute(delete(Setting).where(Setting.key.startswith(f"{name}:")))


async def queued(engine, job_type, *payloads):
    async with make_sessionmaker(engine).begin() as session:
        return [await enqueue(session, job_type, payload) for payload in payloads or [None]]


async def job(engine, job_id):
    async with engine.connect() as connection:
        return (await connection.execute(select(Job).where(Job.id == job_id))).one()


async def eventually(check, seconds=30.0):
    loop = asyncio.get_running_loop()
    deadline = loop.time() + seconds
    while not await check():
        if loop.time() > deadline:
            return False
        await asyncio.sleep(0.1)
    return True


async def test_jobs_run_oldest_first_and_save_real_counts(engine, job_type):
    seen = []

    async def handler(job):
        seen.append(job.payload["n"])
        await job.progress(1, 2, "steps")
        await job.progress(2)

    first, second = await queued(engine, job_type, {"n": 1}, {"n": 2})
    await Worker(engine, {job_type: handler}).run_until_idle()
    assert seen == [1, 2]
    for job_id in (first, second):
        row = await job(engine, job_id)
        assert (row.status, row.attempts, row.progress_done, row.progress_total) == ("done", 1, 2, 2)
        assert row.progress_label == "steps"
        assert row.finished_at is not None


async def test_only_one_worker_runs_a_job_at_a_time(engine, job_type):
    started, release = asyncio.Event(), asyncio.Event()

    async def handler(job):
        started.set()
        await release.wait()

    [job_id] = await queued(engine, job_type)
    first = asyncio.create_task(Worker(engine, {job_type: handler}).run_once())
    try:
        await asyncio.wait_for(started.wait(), 10)
        # A second worker finds nothing it may run. Time-limited, so a broken lock fails here rather than hangs.
        assert await asyncio.wait_for(Worker(engine, {job_type: handler}).run_once(), 10) is False
    finally:
        release.set()
    assert await first is True
    assert (await job(engine, job_id)).attempts == 1


async def test_a_failed_job_keeps_its_error(engine, job_type):
    async def handler(job):
        raise ValueError("no sitemap at that address")

    [job_id] = await queued(engine, job_type)
    await Worker(engine, {job_type: handler}).run_until_idle()
    row = await job(engine, job_id)
    assert (row.status, row.error) == ("failed", "ValueError: no sitemap at that address")


async def test_a_cancelled_job_stops_at_its_next_progress_report(engine, job_type):
    ran = []

    async def handler(job):
        for step in range(3):
            ran.append(step)
            if step == 1:
                async with job.sessions.begin() as session:
                    assert await cancel(session, job.id)
            await job.progress(step + 1, 3)

    [job_id] = await queued(engine, job_type)
    await Worker(engine, {job_type: handler}).run_until_idle()
    assert ran == [0, 1]
    row = await job(engine, job_id)
    assert (row.status, row.progress_done) == ("cancelled", 1)


async def test_a_job_that_keeps_stopping_its_worker_fails_after_three_attempts(engine, job_type):
    called = []

    async def handler(job):
        called.append(job.attempt)

    [job_id] = await queued(engine, job_type)
    async with engine.begin() as connection:
        await connection.execute(update(Job).where(Job.id == job_id).values(status="running", attempts=MAX_ATTEMPTS))
    assert await Worker(engine, {job_type: handler}).run_once() is False
    row = await job(engine, job_id)
    assert called == []
    assert (row.status, row.error) == ("failed", f"Stopped after {MAX_ATTEMPTS} attempts.")


async def test_a_job_whose_worker_was_killed_finishes_exactly_once(engine, job_type):
    """QA promise 16: kill the worker mid-job and restart it; the job finishes exactly once."""
    [job_id] = await queued(engine, job_type)
    hang_at = 2
    process = subprocess.Popen(
        [sys.executable, "-m", "tests.integration.stepped_job", job_type, str(hang_at)],
        cwd=ROOT,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
    )

    async def reached_the_hang():
        return (await job(engine, job_id)).progress_done == hang_at

    try:
        reached = await eventually(reached_the_hang)
    finally:
        process.kill()
        _, stderr = process.communicate()
    assert reached, stderr.decode()[-2000:]

    restarted = Worker(engine, {job_type: stepped(hang_at)})

    async def finished():
        await restarted.run_until_idle()
        return (await job(engine, job_id)).status == "done"

    # Postgres drops the killed worker's lock as soon as it sees the connection close
    assert await eventually(finished, seconds=10)
    row = await job(engine, job_id)
    assert (row.attempts, row.progress_done) == (2, STEPS)
    async with make_sessionmaker(engine)() as session:
        assert await counts(session, job_type) == {**{f"step {n}": 1 for n in range(STEPS)}, "finished": 1}


async def test_a_daily_job_is_queued_once_a_day(engine, job_type):
    sessions = make_sessionmaker(engine)
    async with sessions.begin() as session:
        assert await ensure_daily(session, job_type) is True
    async with sessions.begin() as session:
        assert await ensure_daily(session, job_type) is False  # one is waiting
        await session.execute(update(Job).where(Job.type == job_type).values(status="done"))
    async with sessions.begin() as session:
        assert await ensure_daily(session, job_type) is False  # one ran today
        yesterday = func.now() - dt.timedelta(hours=25)
        await session.execute(update(Job).where(Job.type == job_type).values(created_at=yesterday))
    async with sessions.begin() as session:
        assert await ensure_daily(session, job_type) is True


# The purge (PRD 5.11). These use the rolled-back `session` fixture, except the job itself.


async def test_purge_deletes_conversations_past_retention(session):
    now = await session.scalar(select(func.now()))
    old = Conversation(model="claude-haiku-5-5", prompt_version="1", started_at=now - dt.timedelta(days=91))
    recent = Conversation(model="claude-haiku-5-5", prompt_version="1", started_at=now - dt.timedelta(days=89))
    session.add_all([old, recent])
    await session.flush()
    assert await delete_expired(session, now - dt.timedelta(days=await retention_days(session))) >= 1
    kept = await session.scalars(select(Conversation.id).where(Conversation.id.in_([old.id, recent.id])))
    assert list(kept) == [recent.id]


async def test_the_retention_setting(session):
    assert await retention_days(session) == 90
    session.add(Setting(key="retention_days", value=30))
    await session.flush()
    assert await retention_days(session) == 30
    for wrong in (0, "ninety", True):
        await session.execute(update(Setting).where(Setting.key == "retention_days").values(value=wrong))
        with pytest.raises(PurgeError):
            await retention_days(session)


async def test_the_purge_job_counts_what_it_deletes(engine, job_type):
    sessions = make_sessionmaker(engine)
    async with sessions.begin() as session:
        old = Conversation(model="claude-haiku-5-5", prompt_version="1", started_at=func.now() - dt.timedelta(days=100))
        session.add(old)
    [job_id] = await queued(engine, job_type)
    try:
        await Worker(engine, {job_type: purge}).run_until_idle()
        row = await job(engine, job_id)
        assert (row.status, row.progress_label) == ("done", "conversations")
        assert row.progress_done == row.progress_total >= 1
        async with sessions() as session:
            assert await session.get(Conversation, old.id) is None
    finally:
        async with sessions.begin() as session:
            await session.execute(delete(Conversation).where(Conversation.id == old.id))
