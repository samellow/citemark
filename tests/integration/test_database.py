"""The database the migrations build (Postgres 16 with pgvector).

Needs a running database: `docker compose up -d db`, then `uv run alembic upgrade head`.
"""

import asyncio
import socket
import uuid

import pytest
from sqlalchemy import make_url, text

from citemark.db import migrate
from citemark.db.session import make_engine
from citemark.settings import get_settings


async def _scalar(sql: str, url: str | None = None):
    engine = make_engine(url, isolation_level="AUTOCOMMIT")
    try:
        async with engine.connect() as connection:
            result = await connection.execute(text(sql))
            return result.scalar() if result.returns_rows else None
    finally:
        await engine.dispose()


def test_migrations_install_pgvector():
    assert asyncio.run(_scalar("SELECT extversion FROM pg_extension WHERE extname = 'vector'"))


def test_the_database_is_postgres_16():
    assert asyncio.run(_scalar("SHOW server_version_num")).startswith("16")


def test_serve_migrates_an_empty_database_to_the_newest_revision(monkeypatch):
    """A host's first start (PRD 5.13, T18): the database Render makes is empty, and `citemark
    serve` migrates it before taking a request. Starting again changes nothing."""
    name = f"citemark_migrate_{uuid.uuid4().hex[:8]}"
    fresh = make_url(get_settings().database_url).set(database=name).render_as_string(hide_password=False)
    asyncio.run(_scalar(f'CREATE DATABASE "{name}"'))
    try:
        monkeypatch.setenv("DATABASE_URL", fresh)
        get_settings.cache_clear()
        revision = migrate.upgrade()
        assert asyncio.run(_scalar("SELECT version_num FROM alembic_version", fresh)) == revision
        assert asyncio.run(_scalar("SELECT extname FROM pg_extension WHERE extname = 'vector'", fresh))
        assert migrate.upgrade() == revision
    finally:
        monkeypatch.undo()
        get_settings.cache_clear()
        asyncio.run(_scalar(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)'))


def test_a_database_that_isnt_listening_yet_is_tried_again(monkeypatch):
    """The driver's real error, as on Render when the app started before the database made with
    it: nothing listens on the port. It's waited for, then raised as it came."""
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]  # free, and closed again once the probe is
    slept: list[float] = []
    try:
        monkeypatch.setenv("DATABASE_URL", f"postgresql://citemark@127.0.0.1:{port}/citemark")
        get_settings.cache_clear()
        with pytest.raises(ConnectionRefusedError):
            migrate.upgrade(wait=3, sleep=slept.append, clock=lambda: sum(slept))
    finally:
        monkeypatch.undo()
        get_settings.cache_clear()
    assert slept == [1.0, 2.0]
