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
- generation_registry: one row per issued token, keyed by (table_name, token), with the id of the
  row it was issued to. It has no foreign key, so the row outlives the record it names. Every live
  token is registered. A registration that already names the same row is kept as it is.
- Guards (triggers, and on PostgreSQL three plpgsql functions):
  - a token that is set can never change;
  - a table can never issue a token it has issued before, even after the record that held it was
    deleted, so a record that reuses a deleted record's id gets a new token;
  - registry rows cannot be updated or deleted, and on PostgreSQL the registry cannot be truncated.
  Tokens are unique per table: a dataset and a scenario may hold the same token.

Trust boundary: the guards stop application code, raw SQL and conflict clauses (SQLite OR IGNORE and
OR REPLACE, PostgreSQL ON CONFLICT). They do not stop privileged administration. A PostgreSQL table
owner or superuser can disable or drop the triggers, and whoever owns a SQLite file can change
anything in it. Separating the runtime role from the schema owner is later production hardening.

Restart safety: every step checks the schema first, and an assigned token is never replaced.
- SQLite runs DDL outside the transaction: the first ADD COLUMN commits on its own, and the first
  UPDATE opens the transaction that covers the rest.
- PostgreSQL rolls the whole upgrade back.
- The guards are installed after the last table rebuild, because a SQLite rebuild drops the rebuilt
  table's triggers. An existing guard that matches its definition exactly is kept.
- A registration that names a different row than the live row holding its token, or a registry
  table with an unexpected structure, stops the upgrade. Neither is rewritten.
- The post-conditions are asserted before Alembic records 0005.

Downgrade is for rehearsal only. Production rollback is backup-first (docs/operations.md). Downgrade
drops the guards and the registry, so it destroys the record of issued tokens: after it, reissuing a
deleted token is no longer refused. A full backup restore keeps the registry and the guards. A backup
taken before 0005 and migrated later gets new tokens.
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
REGISTRY = "generation_registry"
# 32 lowercase hex characters on every engine, the same format as the application default.
TOKEN_SQL = {
    "postgresql": "replace(gen_random_uuid()::text, '-', '')",  # built in from PostgreSQL 13
    "sqlite": "lower(hex(randomblob(16)))",
}

# The registry and guard DDL below is also declared in backend/db/generation_guards.py for schemas
# built by create_all. This migration keeps its own copy so it never depends on application code;
# tests/test_generation_identity_migration.py fails if the two copies differ.


def registry_elements() -> list[sa.schema.SchemaItem]:
    """The registry's columns and constraints, as new objects on each call."""
    return [
        sa.Column("table_name", sa.String(32), nullable=False),
        sa.Column("token", sa.String(32), nullable=False),
        sa.Column("row_id", sa.Integer(), nullable=False),
        sa.Column("registered_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("table_name", "token", name="pk_generation_registry"),
        sa.CheckConstraint("table_name IN ('datasets', 'scenarios')", name="ck_generation_registry_table_name"),
    ]


REGISTRY_COLUMNS = ("table_name", "token", "row_id", "registered_at")

# SQLite: trigger name -> (table, CREATE TRIGGER statement). RAISE(ABORT) is used instead of relying on
# a constraint because an outer OR IGNORE / OR REPLACE overrides the conflict policy of the statements
# a trigger runs, but it cannot turn RAISE(ABORT) into a silent skip or an overwrite.
SQLITE_TRIGGERS: dict[str, tuple[str, str]] = {
    "trg_generation_registry_no_overwrite": (
        REGISTRY,
        "CREATE TRIGGER trg_generation_registry_no_overwrite BEFORE INSERT ON generation_registry"
        " WHEN EXISTS (SELECT 1 FROM generation_registry AS r"
        " WHERE r.table_name = NEW.table_name AND r.token = NEW.token)"
        " BEGIN SELECT RAISE(ABORT, 'generation token already issued'); END",
    ),
    "trg_generation_registry_no_update": (
        REGISTRY,
        "CREATE TRIGGER trg_generation_registry_no_update BEFORE UPDATE ON generation_registry"
        " BEGIN SELECT RAISE(ABORT, 'generation_registry is append-only'); END",
    ),
    "trg_generation_registry_no_delete": (
        REGISTRY,
        "CREATE TRIGGER trg_generation_registry_no_delete BEFORE DELETE ON generation_registry"
        " BEGIN SELECT RAISE(ABORT, 'generation_registry is append-only'); END",
    ),
}
for _table in TABLES:
    SQLITE_TRIGGERS[f"trg_{_table}_generation_register"] = (
        _table,
        f"CREATE TRIGGER trg_{_table}_generation_register AFTER INSERT ON {_table}"
        " WHEN NEW.generation IS NOT NULL"
        " BEGIN INSERT INTO generation_registry (table_name, token, row_id)"
        f" VALUES ('{_table}', NEW.generation, NEW.id); END",
    )
    SQLITE_TRIGGERS[f"trg_{_table}_generation_immutable"] = (
        _table,
        f"CREATE TRIGGER trg_{_table}_generation_immutable BEFORE UPDATE ON {_table}"
        " WHEN OLD.generation IS NOT NULL AND OLD.generation IS NOT NEW.generation"
        f" BEGIN SELECT RAISE(ABORT, '{_table}.generation is immutable'); END",
    )

# PostgreSQL (13 or later): function name -> plpgsql body. The conditions live in the bodies, not in
# trigger WHEN clauses, so comparing pg_proc.prosrc verifies them. The register function names the
# registry through the source table's schema, so it works under any search_path.
PG_FUNCTION_SQL = "CREATE OR REPLACE FUNCTION {name}() RETURNS trigger LANGUAGE plpgsql AS $${body}$$"
PG_FUNCTIONS: dict[str, str] = {
    "novaq_generation_register": """
BEGIN
    IF NEW.generation IS NOT NULL THEN
        EXECUTE format(
            'INSERT INTO %I.generation_registry (table_name, token, row_id) VALUES ($1, $2, $3)', TG_TABLE_SCHEMA
        ) USING TG_TABLE_NAME, NEW.generation, NEW.id;
    END IF;
    RETURN NULL;
END
""",
    "novaq_generation_immutable": """
BEGIN
    IF OLD.generation IS NOT NULL AND NEW.generation IS DISTINCT FROM OLD.generation THEN
        RAISE EXCEPTION '%.generation is immutable', TG_TABLE_NAME USING ERRCODE = 'check_violation';
    END IF;
    RETURN NEW;
END
""",
    "novaq_generation_registry_append_only": """
BEGIN
    RAISE EXCEPTION 'generation_registry is append-only (%)', TG_OP USING ERRCODE = 'check_violation';
END
""",
}
# Trigger name -> (table, function, pg_trigger.tgtype, CREATE TRIGGER statement).
# tgtype bits: ROW 1, BEFORE 2, INSERT 4, DELETE 8, UPDATE 16, TRUNCATE 32.
PG_TRIGGERS: dict[str, tuple[str, str, int, str]] = {
    "trg_generation_registry_no_update_delete": (
        REGISTRY,
        "novaq_generation_registry_append_only",
        27,
        "CREATE TRIGGER trg_generation_registry_no_update_delete BEFORE UPDATE OR DELETE ON generation_registry"
        " FOR EACH ROW EXECUTE FUNCTION novaq_generation_registry_append_only()",
    ),
    "trg_generation_registry_no_truncate": (
        REGISTRY,
        "novaq_generation_registry_append_only",
        34,
        "CREATE TRIGGER trg_generation_registry_no_truncate BEFORE TRUNCATE ON generation_registry"
        " FOR EACH STATEMENT EXECUTE FUNCTION novaq_generation_registry_append_only()",
    ),
}
for _table in TABLES:
    PG_TRIGGERS[f"trg_{_table}_generation_register"] = (
        _table,
        "novaq_generation_register",
        5,
        f"CREATE TRIGGER trg_{_table}_generation_register AFTER INSERT ON {_table}"
        " FOR EACH ROW EXECUTE FUNCTION novaq_generation_register()",
    )
    PG_TRIGGERS[f"trg_{_table}_generation_immutable"] = (
        _table,
        "novaq_generation_immutable",
        19,
        f"CREATE TRIGGER trg_{_table}_generation_immutable BEFORE UPDATE ON {_table}"
        " FOR EACH ROW EXECUTE FUNCTION novaq_generation_immutable()",
    )


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


def _normalized(sql: str) -> str:
    return " ".join(sql.split())


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


def _registry_problems() -> list[str]:
    """What is wrong with the registry table's structure; empty when it is exactly as defined."""
    inspector = _inspector()
    if REGISTRY not in inspector.get_table_names():
        return [f"{REGISTRY} is missing"]
    problems = []
    columns = {column["name"]: column for column in inspector.get_columns(REGISTRY)}
    if set(columns) != set(REGISTRY_COLUMNS):
        problems.append(f"{REGISTRY} has columns {sorted(columns)}")
    elif any(column["nullable"] for column in columns.values()):
        problems.append(f"{REGISTRY} has a nullable column")
    if inspector.get_pk_constraint(REGISTRY).get("constrained_columns") != ["table_name", "token"]:
        problems.append(f"{REGISTRY} is not keyed by (table_name, token)")
    if "ck_generation_registry_table_name" not in {check["name"] for check in inspector.get_check_constraints(REGISTRY)}:
        problems.append(f"{REGISTRY} has no table_name check")
    if inspector.get_foreign_keys(REGISTRY):
        problems.append(f"{REGISTRY} has a foreign key")
    return problems


def create_registry() -> None:
    """Create the registry, or accept an existing one only if its structure is exactly as defined."""
    problems = _registry_problems()
    if problems == [f"{REGISTRY} is missing"]:
        op.create_table(REGISTRY, *registry_elements())
    elif problems:
        raise RuntimeError(
            f"{REGISTRY} exists with an unexpected structure ({'; '.join(problems)}). It is not modified "
            "automatically: inspect it, repair or restore it explicitly, then rerun."
        )


def backfill_registry() -> None:
    """Register every live token. Keep exact registrations; stop on any that name a different row."""
    for table in TABLES:
        conflicts = op.get_bind().execute(sa.text(
            f"SELECT s.id, r.row_id FROM {table} AS s JOIN {REGISTRY} AS r"
            f" ON r.table_name = '{table}' AND r.token = s.generation WHERE r.row_id <> s.id ORDER BY s.id"
        )).all()
        if conflicts:
            raise RuntimeError(
                f"{REGISTRY} records live {table} tokens as issued to other rows "
                f"{[tuple(row) for row in conflicts]} (live id, registered id). A registration is never "
                "rewritten automatically: resolve it explicitly, then rerun."
            )
    for table in TABLES:
        op.execute(sa.text(
            f"INSERT INTO {REGISTRY} (table_name, token, row_id) SELECT '{table}', s.generation, s.id"
            f" FROM {table} AS s WHERE NOT EXISTS (SELECT 1 FROM {REGISTRY} AS r"
            f" WHERE r.table_name = '{table}' AND r.token = s.generation)"
        ))


def _guard_names() -> list[str]:
    if op.get_bind().dialect.name == "sqlite":
        return list(SQLITE_TRIGGERS)
    return [*PG_FUNCTIONS, *PG_TRIGGERS]


def _exact_guards() -> set[str]:
    """The guard objects that exist exactly as defined above."""
    bind = op.get_bind()
    if bind.dialect.name == "sqlite":
        rows = bind.execute(sa.text("SELECT name, tbl_name, sql FROM sqlite_master WHERE type = 'trigger'")).all()
        found = {name: (table, _normalized(sql or "")) for name, table, sql in rows}
        return {
            name for name, (table, sql) in SQLITE_TRIGGERS.items() if found.get(name) == (table, _normalized(sql))
        }
    functions: dict[str, list[tuple[Any, ...]]] = {}
    for name, *details in bind.execute(sa.text(
        "SELECT p.proname, p.prosrc, l.lanname, p.prorettype = 'trigger'::regtype, p.prosecdef, p.pronargs,"
        " p.proconfig IS NULL FROM pg_proc AS p JOIN pg_language AS l ON l.oid = p.prolang"
        " JOIN pg_namespace AS n ON n.oid = p.pronamespace"
        " WHERE n.nspname = current_schema() AND p.proname LIKE 'novaq_generation%'"
    )):
        functions.setdefault(name, []).append((_normalized(details[0]), *details[1:]))
    exact = {
        name for name, body in PG_FUNCTIONS.items()
        if functions.get(name) == [(_normalized(body), "plpgsql", True, False, 0, True)]
    }
    triggers = {
        (name, table): tuple(details) for name, table, *details in bind.execute(sa.text(
            "SELECT t.tgname, c.relname, p.proname, pn.nspname = n.nspname, t.tgtype, t.tgenabled,"
            " t.tgqual IS NULL, t.tgnargs, t.tgattr::text FROM pg_trigger AS t"
            " JOIN pg_class AS c ON c.oid = t.tgrelid JOIN pg_namespace AS n ON n.oid = c.relnamespace"
            " JOIN pg_proc AS p ON p.oid = t.tgfoid JOIN pg_namespace AS pn ON pn.oid = p.pronamespace"
            " WHERE NOT t.tgisinternal AND n.nspname = current_schema()"
        ))
    }
    exact |= {
        name for name, (table, function, tgtype, _sql) in PG_TRIGGERS.items()
        if triggers.get((name, table)) == (function, True, tgtype, "O", True, 0, "")
    }
    return exact


def install_guards() -> None:
    """Create each guard object that is missing or differs from its definition; keep exact ones."""
    exact = _exact_guards()
    if op.get_bind().dialect.name == "sqlite":
        for name, (_table, sql) in SQLITE_TRIGGERS.items():
            if name not in exact:
                op.execute(sa.text(f"DROP TRIGGER IF EXISTS {name}"))
                op.execute(sa.text(sql))
        return
    for name, body in PG_FUNCTIONS.items():
        if name not in exact:
            op.execute(sa.text(PG_FUNCTION_SQL.format(name=name, body=body)))
    for name, (table, _function, _tgtype, sql) in PG_TRIGGERS.items():
        if name not in exact:
            op.execute(sa.text(f"DROP TRIGGER IF EXISTS {name} ON {table}"))
            op.execute(sa.text(sql))


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
    registry = _registry_problems()
    problems += registry
    if not registry:
        for table in TABLES:
            if "generation" not in _columns(table):
                continue
            unregistered = _scalar(
                f"SELECT count(*) FROM {table} AS s WHERE NOT EXISTS (SELECT 1 FROM {REGISTRY} AS r"
                f" WHERE r.table_name = '{table}' AND r.token = s.generation AND r.row_id = s.id)"
            )
            if unregistered:
                problems.append(f"{unregistered} {table} rows are not registered in {REGISTRY}")
    exact = _exact_guards()
    missing = [name for name in _guard_names() if name not in exact]
    if missing:
        problems.append("guards missing or altered: " + ", ".join(missing))
    if problems:
        raise RuntimeError("Migration 0005 post-conditions failed: " + "; ".join(problems))


def upgrade() -> None:
    for table in TABLES:
        upgrade_table(table)
    add_dataset_generation()
    create_registry()
    backfill_registry()
    install_guards()  # after the last table rebuild: a SQLite rebuild drops the rebuilt table's triggers
    assert_postconditions()


def remove_guards() -> None:
    """Drop the source-table triggers, then the registry triggers, then the PostgreSQL functions."""
    tables = set(_inspector().get_table_names())
    if op.get_bind().dialect.name == "sqlite":
        order = sorted(SQLITE_TRIGGERS, key=lambda name: SQLITE_TRIGGERS[name][0] == REGISTRY)
        for name in order:
            op.execute(sa.text(f"DROP TRIGGER IF EXISTS {name}"))
        return
    for name in sorted(PG_TRIGGERS, key=lambda name: PG_TRIGGERS[name][0] == REGISTRY):
        table = PG_TRIGGERS[name][0]
        if table in tables:
            op.execute(sa.text(f"DROP TRIGGER IF EXISTS {name} ON {table}"))
    for name in PG_FUNCTIONS:
        op.execute(sa.text(f"DROP FUNCTION IF EXISTS {name}()"))


def assert_downgraded() -> None:
    """Raise if the downgrade left any 0005 object behind."""
    bind = op.get_bind()
    left: list[str] = []
    if REGISTRY in _inspector().get_table_names():
        left.append(REGISTRY)
    if bind.dialect.name == "sqlite":
        names = bind.execute(sa.text("SELECT name FROM sqlite_master WHERE type = 'trigger'")).scalars()
        left += [name for name in names if name in SQLITE_TRIGGERS]
    else:
        names = bind.execute(sa.text(
            "SELECT t.tgname FROM pg_trigger AS t JOIN pg_class AS c ON c.oid = t.tgrelid"
            " JOIN pg_namespace AS n ON n.oid = c.relnamespace WHERE n.nspname = current_schema()"
        )).scalars()
        left += [name for name in names if name in PG_TRIGGERS]
        names = bind.execute(sa.text(
            "SELECT p.proname FROM pg_proc AS p JOIN pg_namespace AS n ON n.oid = p.pronamespace"
            " WHERE n.nspname = current_schema()"
        )).scalars()
        left += [f"{name}()" for name in names if name in PG_FUNCTIONS]
    for table in TABLES:
        left += [f"{table}.{name}" for name in ("generation", "dataset_generation") if name in _columns(table)]
    if left:
        raise RuntimeError("Migration 0005 downgrade left objects behind: " + ", ".join(left))


def downgrade() -> None:
    """Rehearsal only. Production rollback is backup-first (docs/operations.md).

    This destroys the registry, so tokens issued before the downgrade are no longer protected from reuse.
    """
    remove_guards()
    if REGISTRY in _inspector().get_table_names():
        op.drop_table(REGISTRY)
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
    assert_downgraded()
