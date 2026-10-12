"""Migrations at start (PRD 5.13): `citemark serve` brings the database to the newest schema
before it takes a request, so a deploy needs no step of its own."""

from __future__ import annotations

from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory

MIGRATIONS = Path(__file__).resolve().parent / "migrations"


def config() -> Config:
    """Alembic's settings without alembic.ini, whose logging would print plain lines among the
    app's JSON ones. The database comes from DATABASE_URL, as it does for `alembic upgrade`."""
    made = Config()
    made.set_main_option("script_location", str(MIGRATIONS))
    made.set_main_option("path_separator", "os")
    return made


def upgrade() -> str:
    """Migrate to the newest revision, and return it."""
    made = config()
    command.upgrade(made, "head")
    return ScriptDirectory.from_config(made).get_current_head()
