"""Admin user management endpoints (admin role only)."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.api import auth
from backend.api.deps import require_role
from backend.db.models import User
from backend.db.session import get_db

router = APIRouter(prefix="/admin/users", tags=["admin"])

Roles = Literal["admin", "analyst"]


class UserCreate(BaseModel):
    email: str = Field(min_length=3)
    password: str = Field(min_length=1)
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

    model_config = {"from_attributes": True}


@router.post("", response_model=dict, status_code=201)
def create_user(
    payload: UserCreate,
    db: Session = Depends(get_db),
    _admin: User = Depends(require_role("admin")),
) -> dict:
    existing = db.execute(select(User).where(User.email == payload.email)).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(status_code=409, detail="Email already registered.")
    user = User(
        email=payload.email,
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
    return {"user": UserOut.model_validate(user).model_dump()}


@router.get("", response_model=dict)
def list_users(
    db: Session = Depends(get_db),
    _admin: User = Depends(require_role("admin")),
) -> dict:
    users = db.execute(select(User).order_by(User.id)).scalars().all()
    return {"users": [UserOut.model_validate(u).model_dump() for u in users]}


@router.get("/{user_id}", response_model=dict)
def get_user(
    user_id: int,
    db: Session = Depends(get_db),
    _admin: User = Depends(require_role("admin")),
) -> dict:
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found.")
    return {"user": UserOut.model_validate(user).model_dump()}


@router.patch("/{user_id}", response_model=dict)
def patch_user(
    user_id: int,
    payload: UserPatch,
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
    return {"user": UserOut.model_validate(user).model_dump()}
