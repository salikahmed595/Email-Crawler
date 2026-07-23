"""
Async database engine, session factory, and connection pool.
Uses SQLAlchemy 2.0 async engine with asyncpg.
"""

from __future__ import annotations

import os
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from sqlalchemy import event
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.config import get_settings
from app.models.base import Base

_engine: AsyncEngine | None = None
_async_session_factory: async_sessionmaker[AsyncSession] | None = None


def get_engine() -> AsyncEngine:
    """Get or create the async database engine."""
    global _engine
    if _engine is None:
        settings = get_settings()
        is_sqlite = settings.database_url.startswith("sqlite")

        if is_sqlite:
            # Ensure the parent directory for the sqlite file exists.
            db_path = settings.database_url.split(":///")[-1]
            db_dir = os.path.dirname(db_path)
            if db_dir:
                os.makedirs(db_dir, exist_ok=True)

            # SQLite's driver doesn't support the pool_size/max_overflow
            # knobs used for server-based databases like Postgres.
            _engine = create_async_engine(
                settings.database_url,
                echo=settings.is_development,
            )

            # WAL mode + a busy timeout let several concurrent async
            # crawl workers write to the same sqlite file without
            # hitting "database is locked" errors.
            @event.listens_for(_engine.sync_engine, "connect")
            def _set_sqlite_pragmas(dbapi_connection, _record) -> None:
                cursor = dbapi_connection.cursor()
                cursor.execute("PRAGMA journal_mode=WAL")
                cursor.execute("PRAGMA busy_timeout=5000")
                cursor.close()
        else:
            _engine = create_async_engine(
                settings.database_url,
                echo=settings.is_development,
                pool_size=10,
                max_overflow=20,
                pool_pre_ping=True,
                pool_recycle=3600,
            )
    return _engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    """Get or create the async session factory."""
    global _async_session_factory
    if _async_session_factory is None:
        _async_session_factory = async_sessionmaker(
            bind=get_engine(),
            expire_on_commit=False,
            autocommit=False,
            autoflush=False,
            class_=AsyncSession,
        )
    return _async_session_factory


@asynccontextmanager
async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Async context manager that yields a database session.

    Usage:
        async with get_session() as session:
            result = await session.execute(...)
    """
    factory = get_session_factory()
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def init_db() -> None:
    """
    Initialize database — create all tables.
    Use Alembic migrations in production; this is for testing/dev only.
    """
    engine = get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def close_db() -> None:
    """Dispose the database engine and close all connections."""
    global _engine, _async_session_factory
    if _engine is not None:
        await _engine.dispose()
        _engine = None
        _async_session_factory = None
