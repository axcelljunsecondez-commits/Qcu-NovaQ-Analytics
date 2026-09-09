"""Engine and session factory wiring, with env-driven configuration."""

from __future__ import annotations

import os

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from backend.api.settings import Settings, database_url_from_environment

DATABASE_URL = database_url_from_environment()

_engine: Engine | None = None


def create_engine_for(url: str, settings: Settings | None = None) -> Engine:
    """Build an engine for the given URL (tests pass a sqlite URL)."""
    if url.startswith("sqlite"):
        return create_engine(
            url,
            connect_args={"check_same_thread": False},
        )
    pool_size = settings.db_pool_size if settings else int(os.environ.get("DB_POOL_SIZE", "5"))
    max_overflow = settings.db_max_overflow if settings else int(os.environ.get("DB_MAX_OVERFLOW", "5"))
    pool_timeout = settings.db_pool_timeout_seconds if settings else int(os.environ.get("DB_POOL_TIMEOUT_SECONDS", "10"))
    pool_recycle = settings.db_pool_recycle_seconds if settings else int(os.environ.get("DB_POOL_RECYCLE_SECONDS", "1800"))
    connect_timeout = settings.db_connect_timeout_seconds if settings else int(os.environ.get("DB_CONNECT_TIMEOUT_SECONDS", "5"))
    return create_engine(
        url,
        pool_pre_ping=True,
        pool_size=pool_size,
        max_overflow=max_overflow,
        pool_timeout=pool_timeout,
        pool_recycle=pool_recycle,
        connect_args={"connect_timeout": connect_timeout},
    )


def get_engine() -> Engine:
    """Return the process-wide engine, creating it on first use."""
    global _engine
    if _engine is None:
        _engine = create_engine_for(DATABASE_URL)
    return _engine


SessionLocal = sessionmaker(bind=get_engine(), autoflush=False, expire_on_commit=False)


def get_db():
    """FastAPI dependency yielding a database session."""
    db: Session = SessionLocal()
    try:
        yield db
    finally:
        db.close()
