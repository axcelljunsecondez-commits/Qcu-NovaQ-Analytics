"""Public authentication schemas; secrets are intentionally absent."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class UserOut(BaseModel):
    id: int
    email: str
    role: str
    active: bool
    created_at: datetime
    email_verified: bool
    has_password: bool
    auth_methods: list[str]


class AuthConfigOut(BaseModel):
    google_sign_in_enabled: bool
    google_client_id: str | None
