"""Onboarding endpoints for user preferences and first-time setup."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.api.deps import get_current_user
from backend.db.models import User
from backend.db.session import get_db

router = APIRouter(prefix="/onboarding", tags=["onboarding"])


class OnboardingStatus(BaseModel):
    completed: bool
    operation_type: str | None = None
    preferred_terminology: dict = Field(default_factory=dict)


class OnboardingCompleteRequest(BaseModel):
    operation_type: str = Field(min_length=1, max_length=50)
    preferred_terminology: dict = Field(default_factory=dict)


@router.get("/status", response_model=OnboardingStatus)
def get_onboarding_status(
    user: User = Depends(get_current_user),
) -> OnboardingStatus:
    """Get the current user's onboarding status."""
    return OnboardingStatus(
        completed=user.onboarding_completed,
        operation_type=user.operation_type,
        preferred_terminology=user.preferred_terminology or {},
    )


@router.post("/complete", response_model=OnboardingStatus)
def complete_onboarding(
    payload: OnboardingCompleteRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> OnboardingStatus:
    """Mark onboarding as complete and save user preferences."""
    user.onboarding_completed = True
    user.operation_type = payload.operation_type
    user.preferred_terminology = payload.preferred_terminology
    db.commit()
    return OnboardingStatus(
        completed=True,
        operation_type=user.operation_type,
        preferred_terminology=user.preferred_terminology or {},
    )
