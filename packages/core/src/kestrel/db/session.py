"""Async SQLAlchemy engine and session factory."""

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)


def create_db_engine(
    database_url: str,
    pool_size: int = 10,
    max_overflow: int = 20,
    pool_recycle: int = 1800,
    pool_pre_ping: bool = True,
) -> tuple[AsyncEngine, async_sessionmaker[AsyncSession]]:
    """Create an async engine with production-safe pool defaults.

    ``pool_pre_ping`` is enabled by default: SQLAlchemy issues a cheap
    liveness check on checkout and transparently replaces dead connections.
    This prevents ``InterfaceError: connection is closed`` errors against
    managed Postgres providers (Railway, Supabase, etc.) that reap idle
    connections server-side.
    """
    engine = create_async_engine(
        database_url,
        echo=False,
        pool_size=pool_size,
        max_overflow=max_overflow,
        pool_recycle=pool_recycle,
        pool_pre_ping=pool_pre_ping,
    )
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    return engine, session_factory
