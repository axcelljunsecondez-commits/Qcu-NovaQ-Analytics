"""Self-service account endpoints (authenticated, non-admin)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field, StringConstraints
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.api import auth
from backend.api.deps import get_current_user
from backend.db.models import SessionRecord, User
from backend.db.session import get_db

router = APIRouter(prefix="/account", tags=["account"])


class PasswordChange(BaseModel):
    current_password: str = Field(min_length=1, max_length=128)
    new_password: str = Field(min_length=8, max_length=128)


@router.post("/password", response_model=dict)
def change_password(
    payload: PasswordChange,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    """Change the authenticated user's own password.

    Requires proof of the current password. All of the user's OTHER sessions
    are revoked (the session carrying this request is kept), so a leaked
    session cannot outlive a legitimate password change.
    """
    if user.password_hash is None:
        raise auth.AuthApiError(
            400, "password_not_set", "Use the secure Set Password email flow."
        )
    if not auth.verify_password(payload.current_password, user.password_hash):
        raise HTTPException(status_code=401, detail="Current password is incorrect.")

    user.password_hash = auth.hash_password(payload.new_password)
    current_token = request.cookies.get(request.app.state.settings.session_cookie_name)
    query = select(SessionRecord).where(SessionRecord.user_id == user.id)
    if current_token:
        query = query.where(SessionRecord.token_hash != auth.hash_token(current_token))
    now = datetime.now(timezone.utc)
    for record in db.execute(query).scalars().all():
        if record.revoked_at is None:
            record.revoked_at = now
    db.commit()
    request.app.state.logger.info(
        "event=password_change request_id=%s outcome=success user_id=%s",
        getattr(request.state, "request_id", "unknown"),
        user.id,
    )
    return {"detail": "Password changed."}


# Optional preferences (spec 2026-10-09 B1, D2). Unlike POST /onboarding/complete,
# these endpoints never read or write ``onboarding_completed``, and they are not
# under a CSRF-exempt prefix. The 50-character limit matches ``users.operation_type``.
PreferenceText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=50)]


class PreferredTerminology(BaseModel):
    model_config = ConfigDict(extra="forbid")

    operation_label: PreferenceText | None = None
    service_point: PreferenceText | None = None
    service_point_label: PreferenceText | None = None
    service_point_label_singular: PreferenceText | None = None
    customer: PreferenceText | None = None
    customer_label: PreferenceText | None = None
    customer_label_singular: PreferenceText | None = None


class PreferencesUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    operation_type: PreferenceText | None = None
    preferred_terminology: PreferredTerminology = Field(default_factory=PreferredTerminology)


class PreferencesOut(BaseModel):
    operation_type: str | None = None
    # Values saved earlier by onboarding are returned as stored.
    preferred_terminology: dict = Field(default_factory=dict)


def _preferences(user: User) -> PreferencesOut:
    return PreferencesOut(
        operation_type=user.operation_type,
        preferred_terminology=user.preferred_terminology or {},
    )


@router.get("/preferences", response_model=PreferencesOut)
def get_preferences(user: User = Depends(get_current_user)) -> PreferencesOut:
    """Return the signed-in user's saved optional preferences (empty when never saved)."""
    return _preferences(user)


@router.put("/preferences", response_model=PreferencesOut)
def put_preferences(
    payload: PreferencesUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> PreferencesOut:
    """Replace the signed-in user's optional preferences exactly as sent.

    Omitted or null fields are cleared; nothing is filled in on the user's behalf.
    """
    user.operation_type = payload.operation_type
    user.preferred_terminology = payload.preferred_terminology.model_dump(exclude_none=True)
    db.commit()
    return _preferences(user)
