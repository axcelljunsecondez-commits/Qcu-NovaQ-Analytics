"""Engine and session factory wiring, with env-driven configuration."""

from __future__ import annotations

import os

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql+psycopg://novaq:novaq@localhost:5432/novaq",
)

_engine: Engine | None = None


def create_engine_for(url: str) -> Engine:
    """Build an engine for the given URL (tests pass a sqlite URL)."""
    if url.startswith("sqlite"):
        return create_engine(
            url,
            connect_args={"check_same_thread": False},
        )
    return create_engine(url, pool_pre_ping=True)


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
