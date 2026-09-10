"""Self-service account endpoints (authenticated, non-admin)."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
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
