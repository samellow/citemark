"""Migrations at start (PRD 5.13): `citemark serve` brings the database to the newest schema
before it takes a request, so a deploy needs no step of its own."""

from __future__ import annotations

import itertools
import time
from collections.abc import Callable
from pathlib import Path

import asyncpg
import structlog
from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory

log = structlog.get_logger()

MIGRATIONS = Path(__file__).resolve().parent / "migrations"
WAIT = 60.0  # seconds a database that isn't accepting connections yet is waited for
PAUSES = (1.0, 2.0, 4.0, 8.0)  # between tries; the last one repeats
# A database that's still starting: nothing listens yet, its name doesn't resolve yet, or it
# answers that it's starting up. A wrong password or a missing database is none of these.
NOT_READY = (OSError, asyncpg.CannotConnectNowError, asyncpg.ConnectionDoesNotExistError)


def config() -> Config:
    """Alembic's settings without alembic.ini, whose logging would print plain lines among the
    app's JSON ones. The database comes from DATABASE_URL, as it does for `alembic upgrade`."""
    made = Config()
    made.set_main_option("script_location", str(MIGRATIONS))
    made.set_main_option("path_separator", "os")
    return made


def _not_ready(error: BaseException) -> bool:
    """Whether the error, or one it wraps, says the database isn't accepting connections yet."""
    seen: set[int] = set()
    waiting = [error]
    while waiting:
        each = waiting.pop()
        if id(each) in seen:
            continue
        seen.add(id(each))
        if isinstance(each, NOT_READY):
            return True
        # SQLAlchemy keeps the driver's error as .orig, and the driver's own under that
        waiting += [inner for inner in (each.__cause__, each.__context__, getattr(each, "orig", None)) if inner]
    return False


def upgrade(
    *, wait: float = WAIT, sleep: Callable[[float], None] = time.sleep, clock: Callable[[], float] = time.monotonic
) -> str:
    """Migrate to the newest revision, and return it.

    A database that isn't accepting connections yet is tried again for up to `wait` seconds. On a
    host the app can start a few seconds before a database made with it does: the demo's first
    deploy on Render failed that way (2026-10-13). Any other error stops the start at once."""
    made = config()
    deadline = clock() + wait
    for attempt in itertools.count():
        try:
            command.upgrade(made, "head")
            break
        except Exception as exc:
            if not _not_ready(exc) or clock() >= deadline:
                raise
            # The error's type only: its text holds the database's address
            log.warning("database_not_ready", error=type(exc).__name__, attempt=attempt + 1)
            sleep(PAUSES[min(attempt, len(PAUSES) - 1)])
    return ScriptDirectory.from_config(made).get_current_head()
