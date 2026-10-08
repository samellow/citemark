"""The database the migrations build (Postgres 16 with pgvector).

Needs a running database: `docker compose up -d db`, then `uv run alembic upgrade head`.
"""

import asyncio

from sqlalchemy import text

from citemark.db.session import make_engine


async def _scalar(sql: str):
    engine = make_engine()
    try:
        async with engine.connect() as connection:
            return (await connection.execute(text(sql))).scalar_one()
    finally:
        await engine.dispose()


def test_migrations_install_pgvector():
    assert asyncio.run(_scalar("SELECT extversion FROM pg_extension WHERE extname = 'vector'"))


def test_the_database_is_postgres_16():
    assert asyncio.run(_scalar("SHOW server_version_num")).startswith("16")
