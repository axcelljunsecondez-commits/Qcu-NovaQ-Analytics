"""Idempotent admin bootstrap for fresh deployments.

Usage:
    python -m backend.db.seed --email admin@example.com --password secret --role admin
"""

from __future__ import annotations

import argparse
import sys

from argon2 import PasswordHasher
from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

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


def seed_user(email: str, password: str, role: str = "admin") -> str:
    """Create or update a bootstrap user. Returns 'created' or 'updated'."""
    engine = get_engine()
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    with Session() as db:
        existing = db.execute(select(User).where(User.email == email)).scalar_one_or_none()
        password_hash = hash_password(password)
        if existing is None:
            db.add(User(email=email, password_hash=password_hash, role=role, active=True))
            db.commit()
            return "created"
        existing.password_hash = password_hash
        existing.role = role
        existing.active = True
        db.commit()
        return "updated"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Bootstrap an admin user.")
    parser.add_argument("--email", required=True)
    parser.add_argument("--password", required=True)
    parser.add_argument("--role", default="admin", choices=["admin", "analyst"])
    args = parser.parse_args(argv)
    status = seed_user(args.email, args.password, args.role)
    print(f"User {args.email} {status}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
