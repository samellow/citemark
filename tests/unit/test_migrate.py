"""Migrations at start wait for a database that's still starting (T18). The demo's first deploy
on Render failed without this: the app started a few seconds before the database made with it
accepted connections, and exited on the first refusal."""

import socket

import asyncpg
import pytest
from alembic.script import ScriptDirectory
from sqlalchemy.exc import OperationalError

from citemark.db import migrate

HEAD = ScriptDirectory.from_config(migrate.config()).get_current_head()


class Clock:
    """Time that passes only while the code sleeps."""

    def __init__(self) -> None:
        self.now, self.slept = 0.0, []

    def __call__(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.slept.append(seconds)
        self.now += seconds


def failing(monkeypatch, *errors: Exception) -> list[str]:
    """Alembic's upgrade raising each error in turn, then succeeding. Returns the tries made."""
    left, tries = list(errors), []

    def upgrade(config, revision):
        tries.append(revision)
        if left:
            raise left.pop(0)

    monkeypatch.setattr(migrate.command, "upgrade", upgrade)
    return tries


def wrapped(error: Exception) -> OperationalError:
    """The driver's error as SQLAlchemy raises it: under its own wrapper, kept as .orig."""
    adapted = Exception(str(error))
    adapted.__cause__ = error
    return OperationalError("SELECT 1", {}, adapted)


def test_a_database_still_starting_is_waited_for(monkeypatch):
    """Nothing listening yet, a name that doesn't resolve yet, and Postgres saying it's starting."""
    tries = failing(
        monkeypatch,
        ConnectionRefusedError(111, "Connect call failed ('10.0.0.1', 5432)"),
        socket.gaierror(-2, "Name or service not known"),
        wrapped(asyncpg.CannotConnectNowError("the database system is starting up")),
    )
    clock = Clock()
    assert migrate.upgrade(sleep=clock.sleep, clock=clock) == HEAD
    assert clock.slept == [1.0, 2.0, 4.0] and tries == ["head"] * 4


def test_it_gives_up_after_the_wait_with_the_databases_own_error(monkeypatch):
    failing(monkeypatch, *[ConnectionRefusedError(111, "Connect call failed")] * 50)
    clock = Clock()
    with pytest.raises(ConnectionRefusedError):
        migrate.upgrade(wait=10, sleep=clock.sleep, clock=clock)
    assert clock.slept == [1.0, 2.0, 4.0, 8.0]  # the try after 15 seconds is the last


@pytest.mark.parametrize(
    "error",
    [
        wrapped(asyncpg.InvalidPasswordError('password authentication failed for user "citemark"')),
        wrapped(asyncpg.InvalidCatalogNameError('database "citemark" does not exist')),
        RuntimeError("a migration's own failure"),
    ],
)
def test_any_other_error_stops_the_start_at_once(monkeypatch, error):
    """Waiting can't fix a wrong password, a missing database or a broken migration."""
    tries = failing(monkeypatch, error)
    clock = Clock()
    with pytest.raises(type(error)):
        migrate.upgrade(sleep=clock.sleep, clock=clock)
    assert clock.slept == [] and tries == ["head"]
