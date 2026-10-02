"""Generation-token registry and guards for schemas built by ``create_all`` (spec 2026-09-26).

Migration 0005 installs the same registry and guards on migrated databases. It keeps its own copy of
this DDL so it never depends on application code, and tests/test_generation_identity_migration.py
fails if the two copies differ. The migration's docstring describes what the guards refuse and the
trust boundary they stop at.

``create_all`` installs the guards only in the call that also creates datasets and scenarios, so the
tables and their guards are created together. It refuses to add the registry to tables that already
exist, because their tokens must be registered first, and that is migration 0005's job. Nothing here
is reachable through the API.
"""

from __future__ import annotations

from typing import Any

import sqlalchemy as sa

TABLES = ("datasets", "scenarios")
REGISTRY = "generation_registry"


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


# SQLite: trigger name -> (table, CREATE TRIGGER statement).
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

# PostgreSQL: function name -> plpgsql body.
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


def create_statements(dialect: str) -> list[str]:
    """Every statement that creates the guards on a new schema, in order."""
    if dialect == "sqlite":
        return [sql for _table, sql in SQLITE_TRIGGERS.values()]
    if dialect == "postgresql":
        functions = [PG_FUNCTION_SQL.format(name=name, body=body) for name, body in PG_FUNCTIONS.items()]
        return functions + [sql for _table, _function, _tgtype, sql in PG_TRIGGERS.values()]
    raise RuntimeError(f"Generation guards do not support the {dialect!r} dialect.")


def _refuse_existing_tables(_metadata: sa.MetaData, _connection: Any, tables: Any = (), **_kw: Any) -> None:
    names = {table.name for table in tables}
    if REGISTRY in names and not set(TABLES) <= names:
        raise RuntimeError(
            f"create_all would add {REGISTRY} to existing datasets and scenarios tables, whose tokens "
            "are not registered. Run migration 0005 (alembic upgrade head) on this database instead."
        )


def _install_guards(_registry: sa.Table, connection: Any, **_kw: Any) -> None:
    for statement in create_statements(connection.dialect.name):
        connection.execute(sa.text(statement))


def register(metadata: sa.MetaData) -> sa.Table:
    """Declare the registry on ``metadata`` and hook the guards into ``create_all``."""
    registry = sa.Table(REGISTRY, metadata, *registry_elements())
    for name in TABLES:
        # Created after, and dropped before, the tables its guards are attached to.
        registry.add_is_dependent_on(metadata.tables[name])
    sa.event.listen(metadata, "before_create", _refuse_existing_tables)
    sa.event.listen(registry, "after_create", _install_guards)
    return registry
