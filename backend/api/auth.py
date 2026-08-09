"""Password hashing, session lifecycle, and cookie handling."""

from __future__ import annotations

import hashlib
import secrets
from datetime import UTC, datetime, timedelta, timezone

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.db.models import SessionRecord, User

_hasher = PasswordHasher()


def hash_password(password: str) -> str:
    """Hash a plaintext password with argon2id."""
    return _hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    """Verify a plaintext password against an argon2id hash."""
    try:
        return _hasher.verify(password_hash, password)
    except (VerifyMismatchError, InvalidHashError):
        return False


def hash_token(token: str) -> bytes:
    """Return the SHA-256 digest used as the stored session key."""
    return hashlib.sha256(token.encode()).digest()


def _as_aware(value: datetime) -> datetime:
    """Normalize naive datetimes (sqlite) to UTC-aware for comparisons."""
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value


def create_session(db: Session, user_id: int, ttl_hours: float) -> str:
    """Create a session record and return its plaintext token (shown once)."""
    token = secrets.token_urlsafe(32)
    record = SessionRecord(
        user_id=user_id,
        token_hash=hash_token(token),
        expires_at=datetime.now(UTC) + timedelta(hours=ttl_hours),
    )
    db.add(record)
    db.commit()
    return token


def resolve_session_user(db: Session, token: str | None) -> User | None:
    """Resolve a token to its user, or None if invalid/expired/revoked/inactive."""
    if not token:
        return None
    record = db.execute(
        select(SessionRecord).where(SessionRecord.token_hash == hash_token(token))
    ).scalar_one_or_none()
    if record is None:
        return None
    now = datetime.now(UTC)
    if record.revoked_at is not None or _as_aware(record.expires_at) <= now:
        return None
    user = db.get(User, record.user_id)
    if user is None or not user.active:
        return None
    record.last_seen_at = now
    db.commit()
    return user


def revoke_session(db: Session, token: str | None) -> None:
    """Revoke the session identified by the given token, if any."""
    if not token:
        return
    record = db.execute(
        select(SessionRecord).where(SessionRecord.token_hash == hash_token(token))
    ).scalar_one_or_none()
    if record is not None and record.revoked_at is None:
        record.revoked_at = datetime.now(UTC)
        db.commit()


def revoke_all_sessions(db: Session, user_id: int) -> None:
    """Revoke every non-revoked session belonging to a user."""
    records = db.execute(
        select(SessionRecord).where(SessionRecord.user_id == user_id)
    ).scalars().all()
    now = datetime.now(UTC)
    for record in records:
        if record.revoked_at is None:
            record.revoked_at = now
    db.commit()
