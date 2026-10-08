"""Integration tests run against the database at DATABASE_URL, migrated to head.

Each test runs inside a transaction that's rolled back afterwards, so nothing it writes is
kept. That matters here, since even a test can't delete a chunk.
"""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.pool import NullPool

from citemark.db.session import make_engine


@pytest.fixture
async def connection():
    engine = make_engine(poolclass=NullPool)
    try:
        async with engine.connect() as connection:
            transaction = await connection.begin()
            yield connection
            await transaction.rollback()
    finally:
        await engine.dispose()


@pytest.fixture
async def session(connection):
    async with AsyncSession(
        bind=connection, join_transaction_mode="create_savepoint", expire_on_commit=False
    ) as session:
        yield session


@pytest.fixture
def sessions(connection) -> async_sessionmaker[AsyncSession]:
    """Sessions for code that opens its own transactions, as a job does. Each commit goes to a
    savepoint inside the test's transaction, so it's rolled back with everything else."""
    return async_sessionmaker(bind=connection, join_transaction_mode="create_savepoint", expire_on_commit=False)
