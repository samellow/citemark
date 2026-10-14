"""Alembic runs with the app's own settings and async engine."""

import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy.engine import Connection
from sqlalchemy.pool import NullPool

from citemark.db.models import Base
from citemark.db.session import make_engine
from citemark.settings import get_settings

if context.config.config_file_name:
    fileConfig(context.config.config_file_name)

target_metadata = Base.metadata
# Another database than DATABASE_URL's, when `citemark.db.migrate` names one, such as an audit's
URL: str | None = context.config.attributes.get("url")


def run_offline() -> None:
    context.configure(url=URL or get_settings().database_url, target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def _migrate(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_online() -> None:
    engine = make_engine(URL, poolclass=NullPool)
    async with engine.connect() as connection:
        await connection.run_sync(_migrate)
    await engine.dispose()


if context.is_offline_mode():
    run_offline()
else:
    asyncio.run(run_online())
