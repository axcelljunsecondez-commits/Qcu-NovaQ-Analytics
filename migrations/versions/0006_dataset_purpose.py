"""add dataset purpose (B10: planning file vs review-only file)

Revision ID: 0006
Revises: 0005
Create Date: 2026-10-09

Spec: docs/superpowers/specs/2026-10-09-b10-planning-vs-review-file.md (owner-approved 2026-10-09).

``datasets.purpose`` is ``'planning'`` or ``'review'``, not null, default ``'planning'``, so every existing
dataset becomes a planning file and every analysis keeps exactly the current dataset it had.

The column is added in place on both dialects. On SQLite a batch rebuild of ``datasets`` would drop the
generation guard triggers that migration 0005 installs on that table, so SQLite uses ``ALTER TABLE ...
ADD COLUMN`` with an inline CHECK constraint and ``DROP COLUMN`` to downgrade (SQLite 3.35 or later).
Nothing here touches the generation column, its registry or its guards.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

CONSTRAINT = "ck_datasets_purpose"
CHECK = "purpose IN ('planning', 'review')"


def _has_purpose() -> bool:
    return "purpose" in {column["name"] for column in sa.inspect(op.get_bind()).get_columns("datasets")}


def upgrade() -> None:
    if _has_purpose():
        return
    if op.get_bind().dialect.name == "sqlite":
        op.execute(
            "ALTER TABLE datasets ADD COLUMN purpose VARCHAR(16) NOT NULL DEFAULT 'planning' "
            f"CONSTRAINT {CONSTRAINT} CHECK ({CHECK})"
        )
        return
    op.add_column(
        "datasets",
        sa.Column("purpose", sa.String(16), nullable=False, server_default=sa.text("'planning'")),
    )
    op.create_check_constraint(CONSTRAINT, "datasets", CHECK)


def downgrade() -> None:
    if not _has_purpose():
        return
    if op.get_bind().dialect.name == "sqlite":
        op.execute("ALTER TABLE datasets DROP COLUMN purpose")
        return
    op.drop_constraint(CONSTRAINT, "datasets", type_="check")
    op.drop_column("datasets", "purpose")
