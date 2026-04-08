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
) -> tuple[AsyncEngine, async_sessionmaker[AsyncSession]]:
    engine = create_async_engine(
        database_url,
        echo=False,
        pool_size=pool_size,
        max_overflow=max_overflow,
        pool_recycle=pool_recycle,
    )
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    return engine, session_factory
