"""Async engine + session management.

A single lazily-created engine/sessionmaker per process. ``get_session`` is the
FastAPI dependency; ``session_scope`` is the equivalent for workers/scripts.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from functools import lru_cache

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from captureos.config import get_settings


@lru_cache
def get_engine() -> AsyncEngine:
    settings = get_settings()
    return create_async_engine(
        settings.database_url,
        echo=settings.db_echo,
        pool_pre_ping=True,
        future=True,
        # Neon's pooled connection runs PgBouncer in transaction mode, which is incompatible
        # with asyncpg's server-side prepared statement cache (DuplicatePreparedStatementError
        # under load). Disabling it is a safe no-op against any non-pooled Postgres (local
        # Docker, CI), so this applies unconditionally rather than behind an env-specific flag.
        connect_args={"statement_cache_size": 0},
    )


@lru_cache
def get_sessionmaker() -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(
        bind=get_engine(),
        expire_on_commit=False,
        autoflush=False,
    )


async def get_session() -> AsyncIterator[AsyncSession]:
    """FastAPI dependency. Commits on success, rolls back on error."""
    sessionmaker = get_sessionmaker()
    async with sessionmaker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


@asynccontextmanager
async def session_scope() -> AsyncIterator[AsyncSession]:
    """Context manager for non-request code (workers, scripts, seeds)."""
    sessionmaker = get_sessionmaker()
    async with sessionmaker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
