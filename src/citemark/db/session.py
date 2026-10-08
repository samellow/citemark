"""The async engine and sessions (SQLAlchemy 2)."""

from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from citemark.settings import get_settings


def make_engine(url: str | None = None, **kwargs: Any) -> AsyncEngine:
    return create_async_engine(url or get_settings().database_url, pool_pre_ping=True, **kwargs)


def make_sessionmaker(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, expire_on_commit=False)
