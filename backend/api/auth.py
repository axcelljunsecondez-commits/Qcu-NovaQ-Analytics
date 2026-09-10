"""Password hashing, session lifecycle, and cookie handling."""

from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from backend.db.models import AuthChallenge, SessionRecord, User

if TYPE_CHECKING:
    from backend.api.settings import Settings

_hasher = PasswordHasher()


def hash_password(password: str) -> str:
    """Hash a plaintext password with argon2id."""
    return _hasher.hash(password)


def normalize_email(email: str) -> str:
    """Canonical email key used by every account-creation and lookup path."""
    return email.strip().casefold()


def verify_password(password: str, password_hash: str | None) -> bool:
    """Verify a plaintext password against an argon2id hash."""
    if password_hash is None:
        return False
    try:
        return _hasher.verify(password_hash, password)
    except (VerifyMismatchError, InvalidHashError):
        return False


def hash_token(token: str) -> bytes:
    """Return the SHA-256 digest used as the stored session key."""
    return hashlib.sha256(token.encode()).digest()


class AuthApiError(Exception):
    def __init__(self, status_code: int, code: str, detail: str) -> None:
        super().__init__(detail)
        self.status_code = status_code
        self.code = code
        self.detail = detail


def user_payload(user: User) -> dict:
    providers = sorted({identity.provider for identity in user.auth_identities})
    methods = (["password"] if user.password_hash is not None else []) + providers
    return {
        "id": user.id,
        "email": user.email,
        "role": user.role,
        "active": user.active,
        "created_at": user.created_at.isoformat(),
        "email_verified": user.email_verified_at is not None,
        "has_password": user.password_hash is not None,
        "auth_methods": methods,
    }


def _as_aware(value: datetime) -> datetime:
    """Normalize naive datetimes (sqlite) to UTC-aware for comparisons."""
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def create_session(db: Session, user_id: int, ttl_hours: float) -> str:
    """Create a session record and return its plaintext token (shown once)."""
    token = secrets.token_urlsafe(32)
    record = SessionRecord(
        user_id=user_id,
        token_hash=hash_token(token),
        expires_at=datetime.now(timezone.utc) + timedelta(hours=ttl_hours),
    )
    db.add(record)
    db.commit()
    return token


def session_response(db: Session, user: User, settings: Settings):
    """Issue the one canonical NovaQ session/cookie response for every login method."""
    from fastapi.responses import JSONResponse

    token = create_session(db, user.id, settings.session_ttl_hours)
    csrf_token = secrets.token_urlsafe(32)
    max_age = int(settings.session_ttl_hours * 3600)
    response = JSONResponse({"user": user_payload(user)})
    for name, value, httponly in (
        (settings.session_cookie_name, token, True),
        (settings.csrf_cookie_name, csrf_token, False),
    ):
        response.set_cookie(
            key=name,
            value=value,
            max_age=max_age,
            httponly=httponly,
            secure=settings.secure_cookies,
            samesite="lax",
            path="/",
        )
    return response


def issue_challenge(
    db: Session,
    *,
    user_id: int | None,
    purpose: str,
    ttl_minutes: int,
    cooldown_seconds: int = 0,
    hourly_limit: int = 0,
) -> str | None:
    """Return a raw single-use challenge, or None when throttled."""
    now = datetime.now(timezone.utc)
    scope = [AuthChallenge.user_id == user_id, AuthChallenge.purpose == purpose]
    if cooldown_seconds:
        latest = db.execute(
            select(AuthChallenge.created_at).where(*scope).order_by(AuthChallenge.created_at.desc())
        ).scalars().first()
        if latest is not None and _as_aware(latest) > now - timedelta(seconds=cooldown_seconds):
            return None
    if hourly_limit:
        count = db.execute(
            select(func.count(AuthChallenge.id)).where(
                *scope, AuthChallenge.created_at >= now - timedelta(hours=1)
            )
        ).scalar_one()
        if count >= hourly_limit:
            return None
    if purpose in {"verify_email", "reset_password"}:
        db.execute(
            update(AuthChallenge)
            .where(*scope, AuthChallenge.consumed_at.is_(None), AuthChallenge.expires_at > now)
            .values(consumed_at=now)
            .execution_options(synchronize_session=False)
        )
    raw = secrets.token_urlsafe(32)
    db.add(
        AuthChallenge(
            user_id=user_id,
            purpose=purpose,
            token_hash=hash_token(raw),
            expires_at=now + timedelta(minutes=ttl_minutes),
        )
    )
    db.commit()
    return raw


def consume_challenge(db: Session, raw: str, purpose: str) -> AuthChallenge | None:
    """Atomically mark one matching live challenge consumed; caller commits its transaction."""
    now = datetime.now(timezone.utc)
    record = db.execute(
        select(AuthChallenge).where(
            AuthChallenge.token_hash == hash_token(raw),
            AuthChallenge.purpose == purpose,
        )
    ).scalar_one_or_none()
    if record is None:
        return None
    result = db.execute(
        update(AuthChallenge)
        .where(
            AuthChallenge.id == record.id,
            AuthChallenge.consumed_at.is_(None),
            AuthChallenge.expires_at > now,
        )
        .values(consumed_at=now)
        .execution_options(synchronize_session=False)
    )
    if getattr(result, "rowcount", 0) != 1:
        db.rollback()
        return None
    return record


def resolve_session_user(db: Session, token: str | None) -> User | None:
    """Resolve a token to its user, or None if invalid/expired/revoked/inactive."""
    if not token:
        return None
    record = db.execute(
        select(SessionRecord).where(SessionRecord.token_hash == hash_token(token))
    ).scalar_one_or_none()
    if record is None:
        return None
    now = datetime.now(timezone.utc)
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
        record.revoked_at = datetime.now(timezone.utc)
        db.commit()


def revoke_all_sessions(db: Session, user_id: int) -> None:
    """Revoke every non-revoked session belonging to a user."""
    records = db.execute(
        select(SessionRecord).where(SessionRecord.user_id == user_id)
    ).scalars().all()
    now = datetime.now(timezone.utc)
    for record in records:
        if record.revoked_at is None:
            record.revoked_at = now
    db.commit()
