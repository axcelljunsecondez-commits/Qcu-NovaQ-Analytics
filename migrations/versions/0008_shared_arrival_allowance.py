"""Save the Shared Queue arrival allowance outside analytical Setup.

Revision ID: 0008
Revises: 0007
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0008"
down_revision: str | None = "0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLE = "analysis_projects"
COLUMN = "shared_arrival_allowance_minutes"
CONSTRAINT = "ck_analysis_projects_shared_arrival_allowance"
CHECK = "shared_arrival_allowance_minutes IN (0, 15, 30, 45, 60)"


def _has_column() -> bool:
    return COLUMN in {column["name"] for column in sa.inspect(op.get_bind()).get_columns(TABLE)}


def upgrade() -> None:
    if _has_column():
        return
    if op.get_bind().dialect.name == "sqlite":
        op.execute(f"ALTER TABLE {TABLE} ADD COLUMN {COLUMN} INTEGER NOT NULL DEFAULT 0 "
                   f"CONSTRAINT {CONSTRAINT} CHECK ({CHECK})")
        return
    op.add_column(TABLE, sa.Column(COLUMN, sa.Integer(), nullable=False, server_default="0"))
    op.create_check_constraint(CONSTRAINT, TABLE, CHECK)


def downgrade() -> None:
    if not _has_column():
        return
    if op.get_bind().dialect.name != "sqlite":
        op.drop_constraint(CONSTRAINT, TABLE, type_="check")
    op.drop_column(TABLE, COLUMN)
