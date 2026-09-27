"""add generation identity to datasets and scenarios

Revision ID: 0005
Revises: 0004
Create Date: 2026-09-28

Spec: docs/superpowers/specs/2026-09-26-generation-identity-contract.md, section 5.

What this migration writes:
- datasets.generation and scenarios.generation: a newly assigned token is written into every
  existing row. The column then becomes NOT NULL and unique, with a database default for inserts
  that omit it. A token identifies the row as it exists at migration time. It says nothing about
  jobs that referenced the row earlier, so no job row is written.
- scenarios.dataset_generation: added as nullable, with no default, and not backfilled. Which
  dataset generation a legacy save verified cannot be established, so it stays NULL.

Restart safety: every step checks the schema first, and an assigned token is never replaced.
- SQLite runs DDL outside the transaction: the first ADD COLUMN commits on its own, and the first
  UPDATE opens the transaction that covers the rest.
- PostgreSQL rolls the whole upgrade back.
- The post-conditions are asserted before Alembic records 0005.

Downgrade is for rehearsal only. Production rollback is backup-first (docs/operations.md).
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import sqlalchemy as sa
from alembic import op

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLES = ("datasets", "scenarios")
# 32 lowercase hex characters on every engine, the same format as the application default.
TOKEN_SQL = {
    "postgresql": "replace(gen_random_uuid()::text, '-', '')",  # built in from PostgreSQL 13
    "sqlite": "lower(hex(randomblob(16)))",
}


def _token_sql() -> str:
    bind = op.get_bind()
    dialect = bind.dialect.name
    if dialect not in TOKEN_SQL:
        raise RuntimeError(f"Migration 0005 does not support the {dialect!r} dialect.")
    if dialect == "postgresql" and (bind.dialect.server_version_info or (0,)) < (13,):
        raise RuntimeError("Migration 0005 needs PostgreSQL 13 or later (gen_random_uuid).")
    return TOKEN_SQL[dialect]


def _inspector() -> sa.Inspector:
    # A fresh inspector each time: the schema changes between steps.
    return sa.inspect(op.get_bind())


def _columns(table: str) -> dict[str, Any]:
    return {column["name"]: column for column in _inspector().get_columns(table)}


def _unique_names(table: str) -> set[str | None]:
    return {unique["name"] for unique in _inspector().get_unique_constraints(table)}


def _scalar(sql: str) -> int:
    return int(op.get_bind().execute(sa.text(sql)).scalar() or 0)


def _clear_batch_leftover(table: str) -> None:
    """Drop the copy an interrupted SQLite batch rebuild left behind, only if the original survives."""
    leftover = f"_alembic_tmp_{table}"
    names = set(_inspector().get_table_names())
    if leftover not in names:
        return
    if table not in names:
        raise RuntimeError(
            f"{leftover} exists but {table} does not, so the leftover may hold the only copy of the "
            "rows. It is not dropped automatically: recover it or restore the backup, then rerun."
        )
    op.drop_table(leftover)


def upgrade_table(table: str) -> None:
    """Add, backfill and constrain ``<table>.generation``. Safe to rerun from any partial state."""
    token = _token_sql()
    if op.get_bind().dialect.name == "sqlite":
        _clear_batch_leftover(table)
    if "generation" not in _columns(table):
        op.add_column(table, sa.Column("generation", sa.String(32), nullable=True))
    # Only rows without a token get one: an assigned token is never replaced.
    op.execute(sa.text(f"UPDATE {table} SET generation = {token} WHERE generation IS NULL"))
    duplicated = op.get_bind().execute(sa.text(
        f"SELECT id FROM {table} WHERE generation IN "
        f"(SELECT generation FROM {table} GROUP BY generation HAVING count(*) > 1) ORDER BY id"
    )).scalars().all()
    if duplicated:
        raise RuntimeError(
            f"{table} rows {list(duplicated)} share a generation token. Tokens are never regenerated "
            "automatically: resolve the duplicates explicitly, then rerun."
        )
    constraint = f"uq_{table}_generation"
    column = _columns(table)["generation"]
    if column["nullable"] or not column.get("default") or constraint not in _unique_names(table):
        with op.batch_alter_table(table) as batch:
            batch.alter_column(
                "generation",
                existing_type=sa.String(32),
                nullable=False,
                server_default=sa.text(f"({token})"),
            )
            if constraint not in _unique_names(table):
                batch.create_unique_constraint(constraint, ["generation"])


def add_dataset_generation() -> None:
    if "dataset_generation" not in _columns("scenarios"):
        op.add_column("scenarios", sa.Column("dataset_generation", sa.String(32), nullable=True))


def assert_postconditions() -> None:
    """Raise unless the schema is complete, so Alembic never records 0005 over a partial schema."""
    problems: list[str] = []
    for table in TABLES:
        column = _columns(table).get("generation")
        if column is None:
            problems.append(f"{table}.generation is missing")
            continue
        if column["nullable"]:
            problems.append(f"{table}.generation is nullable")
        if not column.get("default"):
            problems.append(f"{table}.generation has no database default")
        if f"uq_{table}_generation" not in _unique_names(table):
            problems.append(f"{table}.generation has no unique constraint")
        if _scalar(f"SELECT count(*) FROM {table} WHERE generation IS NULL"):
            problems.append(f"{table} has rows without a generation")
    binding = _columns("scenarios").get("dataset_generation")
    if binding is None:
        problems.append("scenarios.dataset_generation is missing")
    elif not binding["nullable"] or binding.get("default"):
        problems.append("scenarios.dataset_generation must be nullable with no default")
    if problems:
        raise RuntimeError("Migration 0005 post-conditions failed: " + "; ".join(problems))


def upgrade() -> None:
    for table in TABLES:
        upgrade_table(table)
    add_dataset_generation()
    assert_postconditions()


def downgrade() -> None:
    """Rehearsal only. Production rollback is backup-first (docs/operations.md)."""
    for table in ("scenarios", "datasets"):
        columns = _columns(table)
        drops = [name for name in ("dataset_generation", "generation") if name in columns]
        constraint = f"uq_{table}_generation"
        has_constraint = constraint in _unique_names(table)
        if not drops and not has_constraint:
            continue
        with op.batch_alter_table(table) as batch:
            if has_constraint:
                batch.drop_constraint(constraint, type_="unique")
            for name in drops:
                batch.drop_column(name)
