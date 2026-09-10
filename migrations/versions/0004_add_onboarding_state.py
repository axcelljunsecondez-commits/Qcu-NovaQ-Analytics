"""add onboarding state to users

Revision ID: 0004
Revises: 0003
Create Date: 2026-09-10
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("users") as batch:
        batch.add_column(sa.Column("onboarding_completed", sa.Boolean(), nullable=False, server_default=sa.text("false")))
        batch.add_column(sa.Column("operation_type", sa.String(50), nullable=True))
        batch.add_column(sa.Column("preferred_terminology", sa.JSON(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("users") as batch:
        batch.drop_column("preferred_terminology")
        batch.drop_column("operation_type")
        batch.drop_column("onboarding_completed")
