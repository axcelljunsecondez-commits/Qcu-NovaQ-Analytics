"""add SaaS authentication identities and challenges

Revision ID: 0003
Revises: 0002
Create Date: 2026-09-09
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _normalize(email: str) -> str:
    return email.strip().casefold()


def upgrade() -> None:
    with op.batch_alter_table("users") as batch:
        batch.add_column(sa.Column("email_normalized", sa.String(255), nullable=True))
        batch.add_column(sa.Column("email_verified_at", sa.DateTime(timezone=True), nullable=True))

    bind = op.get_bind()
    users = sa.table(
        "users",
        sa.column("id", sa.Integer),
        sa.column("email", sa.String),
        sa.column("email_normalized", sa.String),
        sa.column("email_verified_at", sa.DateTime(timezone=True)),
        sa.column("created_at", sa.DateTime(timezone=True)),
    )
    rows = bind.execute(sa.select(users.c.id, users.c.email, users.c.created_at)).mappings().all()
    by_normalized: dict[str, list[int]] = defaultdict(list)
    for row in rows:
        by_normalized[_normalize(str(row["email"]))].append(int(row["id"]))
    collisions = {email: ids for email, ids in by_normalized.items() if len(ids) > 1}
    if collisions:
        detail = "; ".join(f"{email}: user IDs {ids}" for email, ids in sorted(collisions.items()))
        raise RuntimeError(
            "Cannot add normalized-email uniqueness. Resolve these legacy account collisions "
            f"without moving ownership, then rerun migration: {detail}"
        )
    for row in rows:
        bind.execute(
            users.update()
            .where(users.c.id == row["id"])
            .values(
                email_normalized=_normalize(str(row["email"])),
                email_verified_at=row["created_at"] or sa.func.now(),
            )
        )

    with op.batch_alter_table("users") as batch:
        batch.alter_column("email_normalized", existing_type=sa.String(255), nullable=False)
        batch.alter_column("password_hash", existing_type=sa.String(255), nullable=True)
        batch.create_index("ix_users_email_normalized", ["email_normalized"], unique=True)

    op.create_table(
        "auth_identities",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("provider", sa.String(32), nullable=False),
        sa.Column("provider_subject", sa.String(255), nullable=False),
        sa.Column("email_at_link", sa.String(255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("provider", "provider_subject", name="uq_auth_identity_subject"),
        sa.UniqueConstraint("user_id", "provider", name="uq_auth_identity_user_provider"),
    )
    op.create_index("ix_auth_identities_user_id", "auth_identities", ["user_id"])

    op.create_table(
        "auth_challenges",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("purpose", sa.String(32), nullable=False),
        sa.Column("token_hash", sa.LargeBinary(32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_auth_challenges_token_hash", "auth_challenges", ["token_hash"], unique=True)
    op.create_index("ix_auth_challenges_user_purpose", "auth_challenges", ["user_id", "purpose"])


def downgrade() -> None:
    bind = op.get_bind()
    null_passwords = bind.execute(sa.text("SELECT COUNT(*) FROM users WHERE password_hash IS NULL")).scalar_one()
    if null_passwords:
        raise RuntimeError(
            "Cannot downgrade while Google-only users have no password. Set passwords for those accounts first."
        )
    op.drop_index("ix_auth_challenges_user_purpose", table_name="auth_challenges")
    op.drop_index("ix_auth_challenges_token_hash", table_name="auth_challenges")
    op.drop_table("auth_challenges")
    op.drop_index("ix_auth_identities_user_id", table_name="auth_identities")
    op.drop_table("auth_identities")
    with op.batch_alter_table("users") as batch:
        batch.drop_index("ix_users_email_normalized")
        batch.alter_column("password_hash", existing_type=sa.String(255), nullable=False)
        batch.drop_column("email_verified_at")
        batch.drop_column("email_normalized")
