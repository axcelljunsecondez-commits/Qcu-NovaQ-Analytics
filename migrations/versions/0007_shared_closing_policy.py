"""add the saved closing rule for the continuous shared-line run (B4a)

Revision ID: 0007
Revises: 0006
Create Date: 2026-10-12

Spec: docs/superpowers/specs/2026-10-09-b4a-continuous-shared-run-preview.md (owner-approved 2026-10-09,
OD-B4a-1 = A).

``analysis_projects.shared_closing_policy`` is ``'DRAIN'``, ``'HARD_CUTOFF'`` or null (not chosen yet). It
lives outside ``queue_setup_json`` so choosing or changing it never changes the Setup fingerprint, and
every existing analysis starts with no rule chosen (the engine has no default closing rule).

As in 0006, the column is added in place on both dialects: SQLite uses ``ALTER TABLE ... ADD COLUMN`` with
an inline CHECK constraint and ``DROP COLUMN`` to downgrade (SQLite 3.35 or later). No generation guard is
installed on ``analysis_projects``, and nothing here touches one.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0007"
down_revision: str | None = "0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLE = "analysis_projects"
COLUMN = "shared_closing_policy"
CONSTRAINT = "ck_analysis_projects_shared_closing_policy"
CHECK = "shared_closing_policy IS NULL OR shared_closing_policy IN ('DRAIN', 'HARD_CUTOFF')"


def _has_column() -> bool:
    return COLUMN in {column["name"] for column in sa.inspect(op.get_bind()).get_columns(TABLE)}


def upgrade() -> None:
    if _has_column():
        return
    if op.get_bind().dialect.name == "sqlite":
        op.execute(f"ALTER TABLE {TABLE} ADD COLUMN {COLUMN} VARCHAR(16) CONSTRAINT {CONSTRAINT} CHECK ({CHECK})")
        return
    op.add_column(TABLE, sa.Column(COLUMN, sa.String(16), nullable=True))
    op.create_check_constraint(CONSTRAINT, TABLE, CHECK)


def downgrade() -> None:
    if not _has_column():
        return
    if op.get_bind().dialect.name == "sqlite":
        op.execute(f"ALTER TABLE {TABLE} DROP COLUMN {COLUMN}")
        return
    op.drop_constraint(CONSTRAINT, TABLE, type_="check")
    op.drop_column(TABLE, COLUMN)
