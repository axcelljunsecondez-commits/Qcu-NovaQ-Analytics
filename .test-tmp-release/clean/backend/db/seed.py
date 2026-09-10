"""Idempotent admin bootstrap for fresh deployments.

Routine seeding is create-only: if the user already exists it is NEVER
modified and the script prints "<email> exists." — this is expected, not
an error. To deliberately reset an existing user's password/role, add
--force-reset (it is the ONLY way to change an existing admin's password).

Usage:
    python -m backend.db.seed --email admin@example.com --password-file /run/secrets/admin_password
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime, timezone

from argon2 import PasswordHasher
from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from backend.api.auth import normalize_email
from backend.api.settings import env_value
from backend.db.base import Base
from backend.db.models import User
from backend.db.session import get_engine

_hasher = PasswordHasher()


def hash_password(password: str) -> str:
    """Hash a plaintext password with argon2id."""
    return _hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    """Verify a plaintext password against an argon2id hash."""
    try:
        return _hasher.verify(password_hash, password)
    except Exception:
        return False


def seed_user(email: str, password: str, role: str = "admin", force: bool = False) -> str:
    """Create a bootstrap user, or return 'exists' if already present.

    Repeat runs never overwrite an existing user's credentials unless
    ``force`` is set. Returns 'created', 'exists', or 'updated'.
    """
    if os.environ.get("NOVAQ_ENV") == "production" and (
        len(password) < 12 or password in {"admin123", "password", "change-me"}
    ):
        raise ValueError("Bootstrap passwords must be at least 12 characters and non-default")
    engine = get_engine()
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    with Session() as db:
        normalized = normalize_email(email)
        existing = db.execute(
            select(User).where(User.email_normalized == normalized)
        ).scalar_one_or_none()
        if existing is None:
            password_hash = hash_password(password)
            db.add(
                User(
                    email=email.strip(),
                    email_normalized=normalized,
                    email_verified_at=datetime.now(timezone.utc),
                    password_hash=password_hash,
                    role=role,
                    active=True,
                )
            )
            db.commit()
            return "created"
        if not force:
            return "exists"
        existing.password_hash = hash_password(password)
        existing.role = role
        existing.active = True
        db.commit()
        return "updated"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Bootstrap an admin user.")
    parser.add_argument("--email", required=True)
    password = parser.add_mutually_exclusive_group(required=True)
    password.add_argument("--password")
    password.add_argument("--password-file")
    parser.add_argument("--role", default="admin", choices=["admin", "analyst"])
    parser.add_argument(
        "--force-reset",
        action="store_true",
        help=(
            "Deliberate reset path: overwrite an existing user's password and role. "
            "Without this flag an existing user is NEVER modified (seed prints 'exists'). "
            "Only use for an intentional password reset."
        ),
    )
    args = parser.parse_args(argv)
    if args.password_file:
        os.environ["ADMIN_PASSWORD_FILE"] = args.password_file
        resolved_password = env_value("ADMIN_PASSWORD")
    else:
        resolved_password = args.password
    assert resolved_password is not None
    status = seed_user(args.email, resolved_password, args.role, force=args.force_reset)
    print(f"Bootstrap user {status}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
