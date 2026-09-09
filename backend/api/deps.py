"""Shared FastAPI dependencies: current user and role guards."""

from __future__ import annotations

from collections.abc import Callable

from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session

from backend.api import auth
from backend.api.settings import Settings
from backend.db.models import User
from backend.db.session import get_db


def get_settings(request: Request) -> Settings:
    """Expose the app's settings object as a dependency."""
    return request.app.state.settings


def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    """Resolve the session cookie to an authenticated, active user (401 otherwise)."""
    settings: Settings = request.app.state.settings
    token = request.cookies.get(settings.session_cookie_name)
    user = auth.resolve_session_user(db, token)
    if user is None:
        raise HTTPException(status_code=401, detail="Not authenticated.")
    request.state.user_id = user.id
    return user


def require_role(role: str) -> Callable[..., User]:
    """Build a dependency that requires the given role (403 otherwise)."""

    def dependency(user: User = Depends(get_current_user)) -> User:
        if user.role != role:
            raise HTTPException(status_code=403, detail="Insufficient permissions.")
        return user

    return dependency


def user_rate_limit(category: str) -> Callable[..., None]:
    """Rate-limit authenticated work across all sessions owned by one user."""

    def dependency(request: Request, user: User = Depends(get_current_user)) -> None:
        settings: Settings = request.app.state.settings
        limit = getattr(settings, f"rate_limit_{category}")
        retry = request.app.state.rate_limiter.consume(
            f"user:{category}",
            str(user.id),
            limit,
            settings.rate_limit_window_seconds,
        )
        if retry is None:
            return
        request_id = getattr(request.state, "request_id", "unknown")
        request.app.state.logger.warning(
            "event=rate_limited request_id=%s category=%s scope=user",
            request_id,
            category,
        )
        raise HTTPException(
            status_code=429,
            detail="Too many requests. Try again later.",
            headers={"Retry-After": str(retry)},
        )

    return dependency
