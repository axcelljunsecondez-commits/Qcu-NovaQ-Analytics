"""Helper functions for the API test suite (shared via tests.conftest)."""

from __future__ import annotations

import hashlib
from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

from backend.db.models import SessionRecord, User
from backend.db.seed import hash_password

SESSION_COOKIE = "novaq_session"
CSRF_COOKIE = "novaq_csrf"


def make_sessionmaker(engine):
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def create_user(
    engine,
    email: str,
    password: str | None,
    role: str = "analyst",
    active: bool = True,
    verified: bool = True,
) -> User:
    """Insert a user directly and return the ORM object."""
    Session = make_sessionmaker(engine)
    with Session() as db:
        user = User(
            email=email,
            email_normalized=email.strip().casefold(),
            email_verified_at=datetime.now(timezone.utc) if verified else None,
            password_hash=hash_password(password) if password is not None else None,
            role=role,
            active=active,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        return user


def login(client: TestClient, email: str, password: str) -> int:
    """Login through the API; returns status code."""
    response = client.post("/auth/login", json={"email": email, "password": password})
    if response.status_code == 200:
        assert SESSION_COOKIE in client.cookies
        assert CSRF_COOKIE in client.cookies
    return response.status_code


def csrf_header(client: TestClient) -> dict[str, str]:
    """Return the double-submit CSRF header from the stored csrf cookie."""
    token = client.cookies.get(CSRF_COOKIE)
    assert token is not None
    return {"X-CSRF-Token": token}


def clear_cookies(client: TestClient) -> None:
    """Drop all stored cookies (fresh-session boundary in tests)."""
    client.cookies.clear()


def add_session_row(
    engine,
    user_id: int,
    token: str,
    *,
    expires_at: datetime | None = None,
    revoked_at: datetime | None = None,
) -> SessionRecord:
    """Insert a session row directly (for expiry/revocation tests)."""
    Session = make_sessionmaker(engine)
    with Session() as db:
        record = SessionRecord(
            user_id=user_id,
            token_hash=hashlib.sha256(token.encode()).digest(),
            expires_at=expires_at or (datetime.now(timezone.utc) + timedelta(hours=1)),
            revoked_at=revoked_at,
        )
        db.add(record)
        db.commit()
        db.refresh(record)
        return record
