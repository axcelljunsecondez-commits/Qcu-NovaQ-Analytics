"""Admin user management endpoints (admin role only)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.api import auth
from backend.api.deps import require_role, user_rate_limit
from backend.db.models import User
from backend.db.session import get_db

router = APIRouter(
    prefix="/admin/users",
    tags=["admin"],
    dependencies=[Depends(user_rate_limit("admin"))],
)

Roles = Literal["admin", "analyst"]


class UserCreate(BaseModel):
    email: EmailStr = Field(max_length=255)
    password: str = Field(min_length=8, max_length=128)
    role: Roles = "analyst"


class UserPatch(BaseModel):
    role: Roles | None = None
    active: bool | None = None


class UserOut(BaseModel):
    id: int
    email: str
    role: str
    active: bool
    created_at: datetime
    email_verified: bool
    has_password: bool
    auth_methods: list[str]

    @classmethod
    def from_user(cls, user: User) -> UserOut:
        return cls(**auth.user_payload(user))


@router.post("", response_model=dict, status_code=201)
def create_user(
    payload: UserCreate,
    db: Session = Depends(get_db),
    _admin: User = Depends(require_role("admin")),
) -> dict:
    normalized = auth.normalize_email(str(payload.email))
    existing = db.execute(
        select(User).where(User.email_normalized == normalized)
    ).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(status_code=409, detail="Email already registered.")
    user = User(
        email=str(payload.email).strip(),
        email_normalized=normalized,
        email_verified_at=datetime.now(timezone.utc),
        password_hash=auth.hash_password(payload.password),
        role=payload.role,
        active=True,
    )
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Email already registered.")
    db.refresh(user)
    return {"user": UserOut.from_user(user).model_dump()}


@router.get("", response_model=dict)
def list_users(
    db: Session = Depends(get_db),
    _admin: User = Depends(require_role("admin")),
) -> dict:
    users = db.execute(select(User).order_by(User.id)).scalars().all()
    return {"users": [UserOut.from_user(u).model_dump() for u in users]}


@router.get("/{user_id}", response_model=dict)
def get_user(
    user_id: int,
    db: Session = Depends(get_db),
    _admin: User = Depends(require_role("admin")),
) -> dict:
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found.")
    return {"user": UserOut.from_user(user).model_dump()}


@router.patch("/{user_id}", response_model=dict)
def patch_user(
    user_id: int,
    payload: UserPatch,
    request: Request,
    db: Session = Depends(get_db),
    _admin: User = Depends(require_role("admin")),
) -> dict:
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found.")
    if payload.role is not None:
        user.role = payload.role
    if payload.active is not None:
        user.active = payload.active
        if not user.active:
            auth.revoke_all_sessions(db, user.id)
    db.commit()
    db.refresh(user)
    request.app.state.logger.info(
        "event=admin_user_change request_id=%s outcome=success actor_user_id=%s target_user_id=%s",
        getattr(request.state, "request_id", "unknown"),
        _admin.id,
        user.id,
    )
    return {"user": UserOut.from_user(user).model_dump()}
