"""A job of five steps for the restart test (QA promise 16).

Each step saves its work and its progress in one transaction, and counts itself in the
`setting` table, as does the job's finish, so a test can see whether anything ran twice.
Run as a script, it works on jobs of one type and hangs at the given step on the first
attempt, so the test can kill it there:

    python -m tests.integration.stepped_job <job type> <step>
"""

import asyncio
import sys

from sqlalchemy import select, text
from sqlalchemy.pool import NullPool

from citemark.db.models import Setting
from citemark.db.session import make_engine
from citemark.jobs.worker import Handler, Worker

STEPS = 5
COUNT = text(
    "INSERT INTO setting (key, value) VALUES (:key, '1') "
    "ON CONFLICT (key) DO UPDATE SET value = to_jsonb(setting.value::text::int + 1)"
)


def stepped(hang_at: int | None = None) -> Handler:
    async def handler(job):
        for step in range(job.resume_from, STEPS):
            if step == hang_at and job.attempt == 1:
                await asyncio.Event().wait()  # until the process is killed
            async with job.sessions.begin() as session:
                await session.execute(COUNT, {"key": f"{job.type}:step {step}"})
                await job.progress(step + 1, STEPS, "steps", session=session)
        async with job.sessions.begin() as session:
            await session.execute(COUNT, {"key": f"{job.type}:finished"})

    return handler


async def counts(session, job_type):
    rows = await session.execute(select(Setting.key, Setting.value).where(Setting.key.startswith(f"{job_type}:")))
    return {key.removeprefix(f"{job_type}:"): value for key, value in rows}


async def main(job_type: str, hang_at: int) -> None:
    engine = make_engine(poolclass=NullPool)
    try:
        await Worker(engine, {job_type: stepped(hang_at)}).run_until_idle()
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1], int(sys.argv[2])))
