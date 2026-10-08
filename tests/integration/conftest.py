"""Integration tests run against the database at DATABASE_URL, migrated to head.

Each test gets a session inside a transaction that's rolled back afterwards, so nothing
it writes is kept. That matters here, since even a test can't delete a chunk.
"""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.pool import NullPool

from citemark.db.session import make_engine


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
async def session():
    engine = make_engine(poolclass=NullPool)
    try:
        async with engine.connect() as connection:
            transaction = await connection.begin()
            async with AsyncSession(
                bind=connection, join_transaction_mode="create_savepoint", expire_on_commit=False
            ) as session:
                yield session
            await transaction.rollback()
    finally:
        await engine.dispose()
