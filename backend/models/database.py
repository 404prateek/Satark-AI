"""
SQLAlchemy async engine, session factory, declarative Base, and FastAPI dependency.

Engine configuration notes:
  - pool_pre_ping=True: Drops stale connections before use (critical for
    PostgreSQL which terminates idle connections after ~10 minutes).
  - pool_size / max_overflow: Sized for a single-node hackathon deployment;
    raise these for production multi-worker setups.
  - echo only in DEBUG mode to avoid leaking SQL (and passwords) to logs.
"""

from __future__ import annotations

from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from backend.config import get_settings

settings = get_settings()

# ── Engine ────────────────────────────────────────────────────────────────────
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
    pool_recycle=3600,   # recycle connections after 1 h
)

# ── Session factory ───────────────────────────────────────────────────────────
SessionLocal: async_sessionmaker[AsyncSession] = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


# ── Declarative Base ──────────────────────────────────────────────────────────
class Base(DeclarativeBase):
    """Shared declarative base — all ORM models inherit from this."""
    pass


# ── FastAPI dependency ────────────────────────────────────────────────────────
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Yields an async database session per HTTP request.

    Usage in a route:
        @router.get("/items")
        async def list_items(db: AsyncSession = Depends(get_db)):
            ...

    The session is committed on clean exit and rolled back on any exception,
    then always closed regardless of outcome.
    """
    async with SessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
