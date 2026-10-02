"""Generation identity (migration 0005 and the model fields): backfill, defaults, guards, recovery and restore.

Spec: docs/superpowers/specs/2026-09-26-generation-identity-contract.md.

Every ``database`` test runs the real migration chain on SQLite. The ``postgresql`` variants run only
when NOVAQ_TEST_DATABASE_URL names a dedicated database ending in _test; each variant creates and
drops its own database. ``guarded`` tests run on a migrated schema and on a ``create_all`` schema.
Tests that use ``db_engine`` run on the ``create_all`` schema the rest of the suite uses.
"""

from __future__ import annotations

import ast
import contextlib
import importlib.util
import json
import os
import re
import shutil
import uuid
from collections.abc import Iterator, Mapping
from datetime import datetime, timezone
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest
from alembic import command
from alembic.config import Config
from alembic.ddl.impl import DefaultImpl
from alembic.operations import BatchOperations, Operations
from alembic.runtime.migration import HeadMaintainer, MigrationContext
from fastapi.testclient import TestClient
from sqlalchemy import Column, MetaData, String, Table, create_engine, event, insert, inspect, select, text
from sqlalchemy.dialects import postgresql, sqlite
from sqlalchemy.engine import Engine, make_url
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.schema import CreateTable

import backend.db.seed as bootstrap
from backend.api.email_delivery import FakeEmailSender
from backend.api.main import create_app
from backend.api.settings import Settings
from backend.db import generation_guards as guards
from backend.db.base import Base
from backend.db.models import Dataset, Job, Scenario, new_generation
from backend.db.session import create_engine_for
from backend.operations import migration_status
from tests.helpers import create_user, csrf_header, login, make_sessionmaker

REPO_ROOT = Path(__file__).resolve().parents[1]
MIGRATION_FILE = REPO_ROOT / "migrations" / "versions" / "0005_generation_identity.py"
TOKEN = re.compile(r"^[0-9a-f]{32}$")
IDENTITY_TABLES = ("datasets", "scenarios")
SEEDED_TABLES = ("users", "analysis_projects", "datasets", "scenarios", "jobs")
NEW_COLUMNS = {"datasets": {"generation"}, "scenarios": {"generation", "dataset_generation"}}
CSV_GOOD = b"time,lambda,mu,c\n08:00-09:00,30,12,3\n09:00-10:00,45,12,4\n"
REGISTRY = "generation_registry"
DIALECTS = ("sqlite", "postgresql")
BUILDS = ("migrated", "create_all")
MODELS: dict[str, Any] = {"datasets": Dataset, "scenarios": Scenario}
# Seeded rows that no other row references, so they can be deleted on their own.
RETIRED = {"datasets": 22, "scenarios": 32}
# What each engine reports when a guard refuses a statement.
REUSE = r"generation token already issued|pk_generation_registry"
IMMUTABLE = r"generation is immutable"
APPEND_ONLY = r"generation_registry is append-only"


class Database:
    """A disposable database driven through the repository's Alembic chain."""

    def __init__(self, url: str, dialect: str, admin: Engine | None = None) -> None:
        self.url = url
        self.dialect = dialect
        self.admin = admin
        self.build = "migrated"
        self.engine = create_engine(url)
        if dialect == "sqlite":
            event.listen(self.engine, "connect", _enforce_sqlite_foreign_keys)

    def _config(self) -> Config:
        os.environ["DATABASE_URL"] = self.url
        config = Config(str(REPO_ROOT / "alembic.ini"))
        config.set_main_option("script_location", str(REPO_ROOT / "migrations"))
        return config

    def upgrade(self, revision: str = "head") -> None:
        command.upgrade(self._config(), revision)

    def downgrade(self, revision: str) -> None:
        command.downgrade(self._config(), revision)

    def version(self) -> str | None:
        with self.engine.connect() as connection:
            return connection.execute(text("SELECT version_num FROM alembic_version")).scalar()

    def migration_engine(self) -> Engine:
        """An engine configured like migrations/env.py: SQLite foreign keys are not enforced."""
        return create_engine(self.url)

    def execute(self, sql: str, **params: Any) -> None:
        with self.engine.begin() as connection:
            connection.execute(text(sql), params)

    def tables(self) -> set[str]:
        return set(inspect(self.engine).get_table_names())

    def columns(self, table: str) -> dict[str, Any]:
        return {column["name"]: column for column in inspect(self.engine).get_columns(table)}

    def unique_names(self, table: str) -> set[str | None]:
        return {unique["name"] for unique in inspect(self.engine).get_unique_constraints(table)}

    def tokens(self, table: str) -> dict[int, str | None]:
        with self.engine.connect() as connection:
            rows = connection.execute(text(f"SELECT id, generation FROM {table} ORDER BY id")).all()
        return {row[0]: row[1] for row in rows}

    def dataset_generations(self) -> list[str | None]:
        with self.engine.connect() as connection:
            return list(connection.execute(text("SELECT dataset_generation FROM scenarios")).scalars())

    def digest(self, columns: dict[str, list[str]]) -> dict[str, str]:
        """Every row of the given original columns, so any change to pre-0005 data shows up."""
        result = {}
        with self.engine.connect() as connection:
            for table, names in columns.items():
                rows = connection.execute(text(f"SELECT {', '.join(names)} FROM {table} ORDER BY id")).all()
                result[table] = json.dumps([list(row) for row in rows], default=str, sort_keys=True)
        return result

    def schema(self, table: str) -> dict[str, Any]:
        inspector = inspect(self.engine)
        return {
            "columns": {
                column["name"]: (str(column["type"]), column["nullable"], column.get("default"))
                for column in inspector.get_columns(table)
            },
            "primary_key": inspector.get_pk_constraint(table)["constrained_columns"],
            "foreign_keys": sorted(
                (fk.get("name") or "", tuple(fk["constrained_columns"]), fk["referred_table"], tuple(fk["referred_columns"]))
                for fk in inspector.get_foreign_keys(table)
            ),
            "indexes": sorted(
                (index["name"] or "", tuple(index["column_names"]), bool(index["unique"]))
                for index in inspector.get_indexes(table)
            ),
            "unique": sorted(
                (unique["name"] or "", tuple(unique["column_names"]))
                for unique in inspector.get_unique_constraints(table)
            ),
        }

    def copy(self, suffix: str) -> Database:
        """A byte-level copy of this database, standing in for a backup taken now and restored later."""
        self.engine.dispose()
        if self.dialect == "sqlite":
            source = Path(make_url(self.url).database or "")
            target = source.with_name(f"{source.stem}_{suffix}.db")
            shutil.copyfile(source, target)
            return Database(f"sqlite:///{target.as_posix()}", "sqlite")
        assert self.admin is not None
        source_name = make_url(self.url).database
        target_name = f"novaq_generation_{uuid.uuid4().hex}_test"
        with self.admin.connect() as connection:
            _terminate(connection, source_name)
            connection.execute(text(f'CREATE DATABASE "{target_name}" TEMPLATE "{source_name}"'))
        copied = make_url(self.url).set(database=target_name).render_as_string(hide_password=False)
        return Database(copied, "postgresql", self.admin)

    def drop(self) -> None:
        self.engine.dispose()
        if self.dialect == "postgresql":
            assert self.admin is not None
            name = make_url(self.url).database
            with self.admin.connect() as connection:
                _terminate(connection, name)
                connection.execute(text(f'DROP DATABASE IF EXISTS "{name}"'))


def _enforce_sqlite_foreign_keys(dbapi_connection: Any, _record: Any) -> None:
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


def _terminate(connection: Any, database: str | None) -> None:
    connection.execute(
        text("SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname=:database AND pid <> pg_backend_pid()"),
        {"database": database},
    )


@contextlib.contextmanager
def open_database(dialect: str, directory: Path, monkeypatch: Any) -> Iterator[Database]:
    """A new, empty database. PostgreSQL databases (and their copies) are created and dropped here."""
    monkeypatch.setenv("DATABASE_URL", "")
    admin: Engine | None = None
    if dialect == "sqlite":
        directory.mkdir(parents=True, exist_ok=True)
        first = Database(f"sqlite:///{(directory / 'generation.db').as_posix()}", "sqlite")
    else:
        source = os.environ.get("NOVAQ_TEST_DATABASE_URL")
        if not source:
            pytest.skip("NOVAQ_TEST_DATABASE_URL is required for the PostgreSQL variant")
        assert source is not None
        source_url = make_url(source)
        if source_url.get_backend_name() != "postgresql" or not (source_url.database or "").endswith("_test"):
            pytest.fail("The PostgreSQL variant requires a dedicated database ending in _test")
        admin = create_engine(source_url.set(database="postgres"), isolation_level="AUTOCOMMIT")
        name = f"novaq_generation_{uuid.uuid4().hex}_test"
        with admin.connect() as connection:
            connection.execute(text(f'CREATE DATABASE "{name}"'))
        first = Database(source_url.set(database=name).render_as_string(hide_password=False), "postgresql", admin)
    created = [first]
    original_copy = Database.copy

    def tracked_copy(self: Database, suffix: str) -> Database:
        copied = original_copy(self, suffix)
        created.append(copied)
        return copied

    with monkeypatch.context() as patch:
        patch.setattr(Database, "copy", tracked_copy)
        try:
            yield first
        finally:
            for db in created:
                db.drop()
            if admin is not None:
                admin.dispose()


@pytest.fixture(params=DIALECTS)
def database(request, tmp_path, monkeypatch) -> Iterator[Database]:
    with open_database(request.param, tmp_path, monkeypatch) as db:
        yield db


@contextlib.contextmanager
def open_guarded(dialect: str, build: str, directory: Path, monkeypatch: Any) -> Iterator[Database]:
    """Seeded rows on a schema built by migrating through 0005, or by ``create_all``."""
    with open_database(dialect, directory, monkeypatch) as db:
        db.build = build
        if build == "migrated":
            db.upgrade("0004")
            seed(db)
            db.upgrade("head")
        else:
            Base.metadata.create_all(db.engine)
            seed(db, models=True)
        yield db


@pytest.fixture(params=[(dialect, build) for dialect in DIALECTS for build in BUILDS], ids="-".join)
def guarded(request, tmp_path, monkeypatch) -> Iterator[Database]:
    dialect, build = request.param
    with open_guarded(dialect, build, tmp_path, monkeypatch) as db:
        yield db


@pytest.fixture(params=BUILDS)
def sqlite_guarded(request, tmp_path, monkeypatch) -> Iterator[Database]:
    with open_guarded("sqlite", request.param, tmp_path, monkeypatch) as db:
        yield db


@pytest.fixture(params=BUILDS)
def postgres_guarded(request, tmp_path, monkeypatch) -> Iterator[Database]:
    with open_guarded("postgresql", request.param, tmp_path, monkeypatch) as db:
        yield db


def load_migration() -> ModuleType:
    spec = importlib.util.spec_from_file_location("migration_0005_under_test", MIGRATION_FILE)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def seed(db: Database, models: bool = False) -> dict[str, list[str]]:
    """Insert rows through tables reflected from the current revision, or through the model tables.

    The model tables apply the application's token default, which a ``create_all`` schema needs
    because it has no database default. Returns the columns of each seeded table.
    """
    tables: Mapping[str, Table]
    if models:
        tables = Base.metadata.tables
    else:
        meta = MetaData()
        meta.reflect(db.engine, only=SEEDED_TABLES)
        tables = meta.tables
    with db.engine.begin() as connection:
        connection.execute(
            insert(tables["users"]),
            [
                {"id": 1, "email": "one@example.com", "email_normalized": "one@example.com", "password_hash": "x",
                 "role": "analyst", "active": True, "preferred_terminology": {"queue": "lane"}},
                {"id": 2, "email": "two@example.com", "email_normalized": "two@example.com", "password_hash": "x",
                 "role": "analyst", "active": True, "preferred_terminology": None},
            ],
        )
        connection.execute(
            insert(tables["analysis_projects"]),
            [{"id": 10, "user_id": 1, "name": "Store", "queue_setup_json": {"lanes": 3}, "setup_status": "complete"}],
        )
        connection.execute(
            insert(tables["datasets"]),
            [
                {"id": 20 + offset, "user_id": 1 + offset % 2, "analysis_id": 10 if offset < 2 else None,
                 "name": f"dataset {offset}", "source_filename": f"d{offset}.csv", "source_format": "csv",
                 "row_count": offset + 1, "normalized_json": [{"lambda": 30 + offset}],
                 "validation_report_json": {"ok": True}}
                for offset in range(3)
            ],
        )
        connection.execute(
            insert(tables["scenarios"]),
            [
                {"id": 30 + offset, "user_id": 1, "analysis_id": 10 if offset < 2 else None,
                 "dataset_id": 20 + offset if offset < 2 else None, "name": f"scenario {offset}",
                 "settings_json": {"target_utilization": 0.7}, "results_json": {"segments": offset}}
                for offset in range(3)
            ],
        )
        connection.execute(
            insert(tables["jobs"]),
            [
                {"id": 40 + offset, "user_id": 1, "kind": "selected_mc", "status": "succeeded",
                 "params_json": {"dataset_id": 20 + offset, "scenario_id": 30 + offset},
                 "result_json": {"replications": 100 + offset}}
                for offset in range(2)
            ],
        )
    return {name: [column.name for column in tables[name].columns] for name in SEEDED_TABLES}


# Raw inserts for the guard tests: every NOT NULL column without a database default, plus the id.
ROW_SQL = {
    "datasets": (
        "user_id, name, source_filename, source_format, row_count, normalized_json, validation_report_json",
        "1, 'raw', 'raw.csv', 'csv', 0, '[]', '{}'",
    ),
    "scenarios": ("user_id, name, settings_json, results_json", "1, 'raw', '{}', '{}'"),
}
MODEL_REQUIRED: dict[str, dict[str, Any]] = {
    "datasets": {"source_filename": "m.csv", "source_format": "csv"},
    "scenarios": {},
}


def insert_row(db: Database, table: str, row_id: int, token: str | None, verb: str = "INSERT", suffix: str = "") -> None:
    columns, values = ROW_SQL[table]
    db.execute(
        f"{verb} INTO {table} (id, {columns}, generation) VALUES (:id, {values}, :token){suffix}",
        id=row_id, token=token,
    )


# --- reading the registry and the guards from the catalog -----------------------------------------


def normalized(sql: str | None) -> str:
    return " ".join((sql or "").split())


def guard_catalog(engine: Engine) -> dict[str, list[tuple[Any, ...]]]:
    """Every trigger, and on PostgreSQL every function, in the engine's schema, read from the catalog."""
    with engine.connect() as connection:
        if engine.dialect.name == "sqlite":
            rows = connection.execute(text("SELECT name, tbl_name, sql FROM sqlite_master WHERE type = 'trigger'")).all()
            return {"triggers": sorted((name, table, normalized(sql)) for name, table, sql in rows)}
        triggers = connection.execute(text(
            "SELECT t.tgname, c.relname, p.proname, pn.nspname = n.nspname, t.tgtype, t.tgenabled,"
            " t.tgqual IS NULL, t.tgnargs, t.tgattr::text FROM pg_trigger AS t"
            " JOIN pg_class AS c ON c.oid = t.tgrelid JOIN pg_namespace AS n ON n.oid = c.relnamespace"
            " JOIN pg_proc AS p ON p.oid = t.tgfoid JOIN pg_namespace AS pn ON pn.oid = p.pronamespace"
            " WHERE NOT t.tgisinternal AND n.nspname = current_schema()"
        )).all()
        functions = connection.execute(text(
            "SELECT p.proname, p.prosrc, l.lanname, p.prorettype::regtype::text, p.pronargs, p.prosecdef,"
            " p.proconfig IS NULL FROM pg_proc AS p JOIN pg_language AS l ON l.oid = p.prolang"
            " JOIN pg_namespace AS n ON n.oid = p.pronamespace WHERE n.nspname = current_schema()"
        )).all()
    return {
        "triggers": sorted(tuple(row) for row in triggers),
        "functions": sorted((name, normalized(source), *rest) for name, source, *rest in functions),
    }


def expected_catalog(dialect: str) -> dict[str, list[tuple[Any, ...]]]:
    """The catalog that the guards declared in backend/db/generation_guards.py produce."""
    if dialect == "sqlite":
        return {
            "triggers": sorted((name, table, normalized(sql)) for name, (table, sql) in guards.SQLITE_TRIGGERS.items())
        }
    return {
        "triggers": sorted(
            (name, table, function, True, tgtype, "O", True, 0, "")
            for name, (table, function, tgtype, _sql) in guards.PG_TRIGGERS.items()
        ),
        "functions": sorted(
            (name, normalized(body), "plpgsql", "trigger", 0, False, True) for name, body in guards.PG_FUNCTIONS.items()
        ),
    }


def empty_catalog(dialect: str) -> dict[str, list[tuple[Any, ...]]]:
    return {"triggers": []} if dialect == "sqlite" else {"triggers": [], "functions": []}


def registry_rows(engine: Engine) -> dict[tuple[str, str], int]:
    """(table_name, token) -> row_id for every registered token."""
    with engine.connect() as connection:
        rows = connection.execute(text(f"SELECT table_name, token, row_id FROM {REGISTRY}")).all()
    registry = {(table, token): row_id for table, token, row_id in rows}
    assert len(registry) == len(rows)
    return registry


def live_registrations(db: Database) -> dict[tuple[str, str], int]:
    """The registrations the live rows need: (table, token) -> id."""
    return {
        (table, token): row_id
        for table in IDENTITY_TABLES
        for row_id, token in db.tokens(table).items()
        if token is not None
    }


def schema_fingerprint(engine: Engine) -> tuple[Any, ...]:
    """Changes whenever the schema, a guard or the registry changes, even when rewritten identically."""
    with engine.connect() as connection:
        if engine.dialect.name == "sqlite":
            objects: list[Any] = [connection.execute(text("PRAGMA schema_version")).scalar()]
            objects += sorted(tuple(row) for row in connection.execute(text("SELECT type, name, tbl_name, sql FROM sqlite_master")))
        else:
            objects = sorted(tuple(row) for row in connection.execute(text(
                "SELECT 'relation', c.relname, c.oid::text, c.xmin::text FROM pg_class AS c"
                " JOIN pg_namespace AS n ON n.oid = c.relnamespace WHERE n.nspname = current_schema()"
                " UNION ALL SELECT 'column', c.relname || '.' || a.attname, a.attnum::text, a.xmin::text"
                " FROM pg_attribute AS a JOIN pg_class AS c ON c.oid = a.attrelid"
                " JOIN pg_namespace AS n ON n.oid = c.relnamespace WHERE n.nspname = current_schema() AND a.attnum > 0"
                " UNION ALL SELECT 'constraint', co.conname, co.oid::text, co.xmin::text FROM pg_constraint AS co"
                " JOIN pg_namespace AS n ON n.oid = co.connamespace WHERE n.nspname = current_schema()"
                " UNION ALL SELECT 'trigger', t.tgname, t.oid::text, t.xmin::text FROM pg_trigger AS t"
                " JOIN pg_class AS c ON c.oid = t.tgrelid JOIN pg_namespace AS n ON n.oid = c.relnamespace"
                " WHERE n.nspname = current_schema()"
                " UNION ALL SELECT 'function', p.proname, p.oid::text, p.xmin::text FROM pg_proc AS p"
                " JOIN pg_namespace AS n ON n.oid = p.pronamespace WHERE n.nspname = current_schema()"
            )))
        if REGISTRY in inspect(connection).get_table_names():
            objects += sorted(tuple(row) for row in connection.execute(
                text(f"SELECT table_name, token, row_id, CAST(registered_at AS TEXT) FROM {REGISTRY}")
            ))
    return tuple(objects)


def job_rows(db: Database) -> list[tuple[Any, ...]]:
    """Every jobs column as the database stores it: SQLite quote(), PostgreSQL text output."""
    wrap = "quote({})" if db.dialect == "sqlite" else "CAST({} AS TEXT)"
    names = ", ".join(wrap.format(name) for name in db.columns("jobs"))
    with db.engine.connect() as connection:
        return [tuple(row) for row in connection.execute(text(f"SELECT {names} FROM jobs ORDER BY id"))]


def registry_structure(db: Database) -> dict[str, Any]:
    structure = db.schema(REGISTRY)
    structure["checks"] = sorted(
        (check["name"], normalized(check["sqltext"])) for check in inspect(db.engine).get_check_constraints(REGISTRY)
    )
    return structure


# --- the state assertions -------------------------------------------------------------------------


def assert_no_hardening(db: Database) -> None:
    assert REGISTRY not in db.tables()
    assert guard_catalog(db.engine) == empty_catalog(db.dialect)


def assert_complete(db: Database) -> None:
    """The 0005 post-conditions, checked from outside the migration."""
    assert db.version() == "0005"
    for table in IDENTITY_TABLES:
        column = db.columns(table)["generation"]
        assert column["nullable"] is False
        assert column.get("default")
        assert f"uq_{table}_generation" in db.unique_names(table)
        tokens = list(db.tokens(table).values())
        assert all(token is not None and TOKEN.match(token) for token in tokens)
        assert len(set(tokens)) == len(tokens)
    binding = db.columns("scenarios")["dataset_generation"]
    assert binding["nullable"] is True
    assert binding.get("default") is None
    assert not {name for name in db.tables() if name.startswith("_alembic_tmp_")}
    registry = registry_rows(db.engine)
    assert all(registry.get(key) == row_id for key, row_id in live_registrations(db).items())
    assert guard_catalog(db.engine) == expected_catalog(db.dialect)


def assert_untouched(db: Database, before: dict[str, dict[str, Any]]) -> None:
    assert db.version() == "0004"
    for table in IDENTITY_TABLES:
        assert db.schema(table) == before[table]
    assert_no_hardening(db)


def assert_first_column_only(db: Database) -> None:
    """SQLite commits the first ADD COLUMN on its own; everything after it rolls back."""
    assert db.version() == "0004"
    column = db.columns("datasets")["generation"]
    assert column["nullable"] is True
    assert column.get("default") is None
    assert "uq_datasets_generation" not in db.unique_names("datasets")
    assert set(db.tokens("datasets").values()) == {None}
    assert not NEW_COLUMNS["scenarios"] & set(db.columns("scenarios"))
    assert not {name for name in db.tables() if name.startswith("_alembic_tmp_")}
    assert_no_hardening(db)


# --- the backfill and the defaults --------------------------------------------------------------


def test_upgrade_backfills_unique_tokens_without_touching_existing_rows(database):
    database.upgrade("0004")
    columns = seed(database)
    before = database.digest(columns)
    database.upgrade("head")
    assert_complete(database)
    assert database.digest(columns) == before
    assert len(database.tokens("datasets")) == 3
    assert len(database.tokens("scenarios")) == 3
    assert database.dataset_generations() == [None, None, None]
    assert set(database.columns("jobs")) == set(columns["jobs"])
    assert registry_rows(database.engine) == live_registrations(database)


def test_database_default_assigns_a_token_when_an_insert_omits_it(database):
    database.upgrade("0004")
    seed(database)
    database.upgrade("head")
    database.execute(
        "INSERT INTO datasets (id, user_id, name, source_filename, source_format, row_count, normalized_json,"
        " validation_report_json) VALUES (60, 1, 'raw', 'raw.csv', 'csv', 0, '[]', '{}')"
    )
    database.execute(
        "INSERT INTO scenarios (id, user_id, dataset_id, name, settings_json, results_json)"
        " VALUES (61, 1, 60, 'raw', '{}', '{}')"
    )
    assert TOKEN.match(database.tokens("datasets")[60] or "")
    assert TOKEN.match(database.tokens("scenarios")[61] or "")
    assert database.dataset_generations() == [None] * 4
    assert_complete(database)


@pytest.mark.parametrize("table", IDENTITY_TABLES)
def test_duplicate_or_missing_token_is_rejected(database, table):
    database.upgrade("0004")
    seed(database)
    database.upgrade("head")
    existing = next(iter(database.tokens(table).values()))
    with pytest.raises(IntegrityError):
        database.execute(f"UPDATE {table} SET generation = :token WHERE id = (SELECT max(id) FROM {table})", token=existing)
    with pytest.raises(IntegrityError):
        database.execute(f"UPDATE {table} SET generation = NULL WHERE id = (SELECT min(id) FROM {table})")


def test_downgrade_then_upgrade_assigns_new_identities_and_keeps_rows(database):
    database.upgrade("0004")
    columns = seed(database)
    before = database.digest(columns)
    schema_0004 = {table: database.schema(table) for table in IDENTITY_TABLES}
    database.upgrade("head")
    first = {table: database.tokens(table) for table in IDENTITY_TABLES}
    database.downgrade("0004")
    assert_untouched(database, schema_0004)
    assert database.digest(columns) == before
    database.upgrade("head")
    assert_complete(database)
    assert database.digest(columns) == before
    for table in IDENTITY_TABLES:
        assert set(first[table].values()).isdisjoint(database.tokens(table).values())


def test_rebuild_preserves_columns_keys_indexes_and_foreign_keys(database):
    database.upgrade("0004")
    seed(database)
    before = {table: database.schema(table) for table in IDENTITY_TABLES}
    database.upgrade("head")
    for table in IDENTITY_TABLES:
        after = database.schema(table)
        constraint = f"uq_{table}_generation"
        assert set(after["columns"]) - set(before[table]["columns"]) == NEW_COLUMNS[table]
        after["columns"] = {name: value for name, value in after["columns"].items() if name not in NEW_COLUMNS[table]}
        after["indexes"] = [index for index in after["indexes"] if index[0] != constraint]
        after["unique"] = [unique for unique in after["unique"] if unique[0] != constraint]
        assert after == before[table]
    # created_at still defaults, and foreign keys are still enforced after the SQLite table rebuild.
    database.execute(
        "INSERT INTO datasets (id, user_id, name, source_filename, source_format, row_count, normalized_json,"
        " validation_report_json) VALUES (70, 2, 'late', 'late.csv', 'csv', 0, '[]', '{}')"
    )
    with database.engine.connect() as connection:
        assert connection.execute(text("SELECT created_at FROM datasets WHERE id = 70")).scalar() is not None
    with pytest.raises(IntegrityError):
        database.execute(
            "INSERT INTO scenarios (user_id, dataset_id, name, settings_json, results_json)"
            " VALUES (1, 9999, 'orphan', '{}', '{}')"
        )
    with pytest.raises(IntegrityError):
        database.execute(
            "INSERT INTO datasets (user_id, name, source_filename, source_format, row_count, normalized_json,"
            " validation_report_json) VALUES (9999, 'orphan', 'o.csv', 'csv', 0, '[]', '{}')"
        )
    if database.dialect == "sqlite":
        with database.engine.connect() as connection:
            assert connection.execute(text("PRAGMA integrity_check")).scalar() == "ok"
            assert connection.execute(text("PRAGMA foreign_key_check")).all() == []


# --- compatibility between code and schema versions ---------------------------------------------


def test_pre_generation_column_set_still_reads_and_writes_after_upgrade(database):
    """Tables reflected at 0004 (the columns code written before 0005 knows) keep working on 0005.

    This is Core-level evidence about the column set, not a run of the previous application.
    """
    database.upgrade("0004")
    seed(database)
    old = MetaData()
    old.reflect(database.engine, only=IDENTITY_TABLES)
    database.upgrade("head")
    with database.engine.begin() as connection:
        connection.execute(
            insert(old.tables["datasets"]).values(
                id=80, user_id=1, name="old code", source_filename="old.csv", source_format="csv", row_count=0,
                normalized_json=[], validation_report_json={},
            )
        )
        connection.execute(
            insert(old.tables["scenarios"]).values(
                id=81, user_id=1, dataset_id=80, name="old code", settings_json={}, results_json={}
            )
        )
        names = connection.execute(select(old.tables["datasets"].c.name).order_by(old.tables["datasets"].c.id)).scalars()
        assert list(names)[-1] == "old code"
    assert TOKEN.match(database.tokens("datasets")[80] or "")
    assert TOKEN.match(database.tokens("scenarios")[81] or "")
    assert_complete(database)


def test_current_models_fail_on_0004_and_status_check_reports_it(database, monkeypatch):
    database.upgrade("0004")
    seed(database)
    session_factory = make_sessionmaker(database.engine)
    with session_factory() as session:
        session.add(Dataset(user_id=1, name="new", source_filename="n.csv", source_format="csv"))
        with pytest.raises(DBAPIError):
            session.commit()
    with session_factory() as session:
        with pytest.raises(DBAPIError):
            session.get(Scenario, 30)
    monkeypatch.chdir(REPO_ROOT)
    monkeypatch.setenv("DATABASE_URL", database.url)
    with pytest.raises(SystemExit, match=r"expected \['0005'\], got \['0004'\]"):
        migration_status.main()
    database.upgrade("head")
    monkeypatch.setenv("DATABASE_URL", database.url)
    migration_status.main()


def test_application_on_the_migrated_schema_assigns_and_reports_tokens(database, monkeypatch):
    database.upgrade("head")
    engine = create_engine_for(database.url)
    try:
        client = TestClient(create_app(engine=engine, settings=Settings(), email_sender=FakeEmailSender()))
        client.headers["X-NovaQ-Client-Protocol"] = "2"
        create_user(engine, "g@example.com", "pw")
        assert login(client, "g@example.com", "pw") == 200
        supplied = {"generation": "f" * 32, "dataset_generation": "e" * 32}
        body = {"name": "Morning rush", "settings": {"target_utilization": 0.7}, "results": {"segments": 4}}
        created = client.post("/scenarios", headers=csrf_header(client), json={**body, **supplied})
        assert created.status_code == 201
        scenario = created.json()["scenario"]
        assert "dataset_generation" not in scenario
        stored = database.tokens("scenarios")[scenario["id"]]
        assert stored is not None and TOKEN.match(stored) and stored != supplied["generation"]
        assert scenario["generation"] == stored
        assert database.dataset_generations() == [None]
        patched = client.patch(
            f"/scenarios/{scenario['id']}", headers=csrf_header(client), json={"name": "Renamed", **supplied}
        )
        assert patched.status_code == 200
        assert patched.json()["scenario"]["generation"] == stored
        assert database.tokens("scenarios")[scenario["id"]] == stored
        assert database.dataset_generations() == [None]
        uploaded = client.post(
            "/datasets", headers=csrf_header(client), files={"file": ("d.csv", CSV_GOOD, "application/octet-stream")}
        )
        assert uploaded.status_code == 201
        dataset = uploaded.json()["dataset"]
        dataset_token = database.tokens("datasets")[dataset["id"]] or ""
        assert TOKEN.match(dataset_token)
        assert dataset["generation"] == dataset_token
        assert client.get(f"/datasets/{dataset['id']}").json()["dataset"]["generation"] == dataset_token
        assert client.delete(f"/scenarios/{scenario['id']}", headers=csrf_header(client)).status_code == 200
        assert client.delete(f"/datasets/{dataset['id']}", headers=csrf_header(client)).status_code == 200
        assert database.tokens("scenarios") == {}
        assert database.tokens("datasets") == {}
        # Deleting through the API leaves the issued tokens registered.
        assert registry_rows(database.engine) == {
            ("scenarios", stored): scenario["id"],
            ("datasets", dataset_token): dataset["id"],
        }
    finally:
        engine.dispose()


# --- recovery from a failed or partial upgrade --------------------------------------------------


class InjectedFault(RuntimeError):
    pass


FAULTS = (
    "before_any_change",  # the first ADD COLUMN raises before it runs
    "after_first_column",  # datasets.generation exists; the backfill raises before it runs
    "during_backfill",  # the datasets backfill runs, then raises
    "during_constraint",  # declaring the datasets unique constraint raises
    "during_constraint_ddl",  # the constraint DDL fails part-way (SQLite: after the old table was dropped)
    "after_datasets_constraint",  # datasets complete; the scenarios ADD COLUMN raises
    "after_both_constraints",  # both tables complete; the dataset_generation ADD COLUMN raises
    "silent_missing_constraint",  # the scenarios constraint step silently does nothing
    "after_registry_created",  # the registry table is created, then the upgrade raises
    "during_registry_backfill",  # the datasets tokens are registered; registering scenarios raises
    "after_registry_backfill",  # every token is registered; the first guard statement raises
    "after_some_guards",  # two guard triggers exist; the third CREATE TRIGGER raises
    "before_version_recorded",  # the post-conditions pass; recording 0005 in alembic_version raises
    "silent_missing_guard",  # one guard trigger is silently not created
    "silent_missing_registration",  # the scenarios tokens are silently not registered
)
# The post-condition each silent fault must trip, so 0005 is never recorded over it.
SILENT_FAULTS = {
    "silent_missing_constraint": "scenarios.generation has no unique constraint",
    "silent_missing_guard": "guards missing or altered: trg_scenarios_generation_immutable",
    "silent_missing_registration": f"3 scenarios rows are not registered in {REGISTRY}",
}


def upgrade_with_fault(db: Database, monkeypatch, fault: str) -> BaseException:
    """Run the unmodified migration with one fault injected into Alembic from outside it."""
    add_column, execute = Operations.add_column, Operations.execute
    create_table, update_to_step = Operations.create_table, HeadMaintainer.update_to_step
    create_unique = BatchOperations.create_unique_constraint
    rename_table, add_constraint = DefaultImpl.rename_table, DefaultImpl.add_constraint
    created_triggers = 0

    def faulty_add_column(self, table_name, column, *args, **kwargs):
        if (
            fault == "before_any_change"
            or (fault == "after_datasets_constraint" and table_name == "scenarios")
            or (fault == "after_both_constraints" and column.name == "dataset_generation")
        ):
            raise InjectedFault(fault)
        return add_column(self, table_name, column, *args, **kwargs)

    def faulty_execute(self, sqltext, *args, **kwargs):
        nonlocal created_triggers
        sql = str(sqltext)
        backfill = sql.startswith("UPDATE datasets")
        registration = sql.startswith(f"INSERT INTO {REGISTRY}") and "'scenarios'" in sql
        guard = sql.startswith(("DROP TRIGGER", "CREATE TRIGGER", "CREATE OR REPLACE FUNCTION"))
        if sql.startswith("CREATE TRIGGER"):
            created_triggers += 1
        if (
            (fault == "after_first_column" and backfill)
            or (fault == "during_registry_backfill" and registration)
            or (fault == "after_registry_backfill" and guard)
            or (fault == "after_some_guards" and sql.startswith("CREATE TRIGGER") and created_triggers == 3)
        ):
            raise InjectedFault(fault)
        if (fault == "silent_missing_registration" and registration) or (
            fault == "silent_missing_guard" and sql.startswith("CREATE TRIGGER trg_scenarios_generation_immutable ")
        ):
            return None
        result = execute(self, sqltext, *args, **kwargs)
        if fault == "during_backfill" and backfill:
            raise InjectedFault(fault)
        return result

    def faulty_create_table(self, table_name, *args, **kwargs):
        result = create_table(self, table_name, *args, **kwargs)
        if fault == "after_registry_created" and table_name == REGISTRY:
            raise InjectedFault(fault)
        return result

    def faulty_update_to_step(self, step):
        if fault == "before_version_recorded":
            raise InjectedFault(fault)
        return update_to_step(self, step)

    def faulty_create_unique(self, constraint_name, *args, **kwargs):
        if fault == "during_constraint" and constraint_name == "uq_datasets_generation":
            raise InjectedFault(fault)
        if fault == "silent_missing_constraint" and constraint_name == "uq_scenarios_generation":
            return None
        return create_unique(self, constraint_name, *args, **kwargs)

    def faulty_rename_table(self, old_table_name, new_table_name, *args, **kwargs):
        if fault == "during_constraint_ddl" and new_table_name == "datasets":
            raise InjectedFault(fault)
        return rename_table(self, old_table_name, new_table_name, *args, **kwargs)

    def faulty_add_constraint(self, const, *args, **kwargs):
        if fault == "during_constraint_ddl" and getattr(const, "name", None) == "uq_datasets_generation":
            raise InjectedFault(fault)
        return add_constraint(self, const, *args, **kwargs)

    with monkeypatch.context() as patch:
        patch.setattr(Operations, "add_column", faulty_add_column)
        patch.setattr(Operations, "execute", faulty_execute)
        patch.setattr(Operations, "create_table", faulty_create_table)
        patch.setattr(HeadMaintainer, "update_to_step", faulty_update_to_step)
        patch.setattr(BatchOperations, "create_unique_constraint", faulty_create_unique)
        patch.setattr(DefaultImpl, "rename_table", faulty_rename_table)
        patch.setattr(DefaultImpl, "add_constraint", faulty_add_constraint)
        with pytest.raises(RuntimeError) as raised:
            db.upgrade("head")
    return raised.value


@pytest.mark.parametrize("fault", FAULTS)
def test_failed_upgrade_leaves_0004_and_a_retry_completes(database, monkeypatch, fault):
    database.upgrade("0004")
    columns = seed(database)
    before = database.digest(columns)
    schema_0004 = {table: database.schema(table) for table in IDENTITY_TABLES}
    error = upgrade_with_fault(database, monkeypatch, fault)
    if fault in SILENT_FAULTS:
        assert SILENT_FAULTS[fault] in str(error)
    else:
        assert isinstance(error, InjectedFault)
    # PostgreSQL rolls the whole upgrade back. SQLite keeps only the first ADD COLUMN.
    if database.dialect == "postgresql" or fault == "before_any_change":
        assert_untouched(database, schema_0004)
    else:
        assert_first_column_only(database)
    assert database.digest(columns) == before
    database.upgrade("head")
    assert_complete(database)
    assert registry_rows(database.engine) == live_registrations(database)
    assert database.digest(columns) == before
    assert database.dataset_generations() == [None, None, None]
    tokens = {table: database.tokens(table) for table in IDENTITY_TABLES}
    fingerprint = schema_fingerprint(database.engine)
    database.upgrade("head")
    assert {table: database.tokens(table) for table in IDENTITY_TABLES} == tokens
    assert schema_fingerprint(database.engine) == fingerprint


def test_repeated_failures_then_success_assign_each_token_once(database, monkeypatch):
    database.upgrade("0004")
    columns = seed(database)
    before = database.digest(columns)
    for fault in (
        "after_first_column", "after_first_column", "during_backfill", "after_both_constraints",
        "during_registry_backfill", "after_some_guards", "before_version_recorded", "before_version_recorded",
    ):
        upgrade_with_fault(database, monkeypatch, fault)
        assert database.version() == "0004"
        assert_no_hardening(database)
    database.upgrade("head")
    assert_complete(database)
    assert registry_rows(database.engine) == live_registrations(database)
    assert database.digest(columns) == before


STATES = (
    "first_column",  # datasets.generation added, nothing else
    "partial_backfill",  # ... and one datasets row has a token
    "datasets_constrained",  # datasets complete
    "both_constrained",  # datasets and scenarios complete
    "columns_complete",  # every column complete; no registry
    "registry_created",  # the registry exists, holding only a tombstone
    "registry_partial",  # ... and the datasets tokens
    "registry_backfilled",  # every token registered; no guards
    "some_guards",  # only the registry's own guards (and on PostgreSQL the functions)
    "guards_before_rebuild",  # every guard installed while scenarios still needs its rebuild
    "altered_guard",  # complete, but one guard was weakened in place
    "complete_unrecorded",  # everything complete except the alembic_version row
)
REGISTRY_STATES = STATES[STATES.index("registry_created"):]
TOMBSTONE = ("datasets", "b" * 32, 99)  # a token issued to a row deleted since; every retry must keep it
EXPECTED_BATCHES: dict[str, list[str]] = {state: [] for state in STATES} | {
    "first_column": ["datasets", "scenarios"],
    "partial_backfill": ["datasets", "scenarios"],
    "datasets_constrained": ["scenarios"],
    "guards_before_rebuild": ["scenarios"],
}
WEAKENED_GUARD = {
    "sqlite": [
        "DROP TRIGGER trg_datasets_generation_immutable",
        "CREATE TRIGGER trg_datasets_generation_immutable BEFORE UPDATE ON datasets WHEN 0 BEGIN SELECT 1; END",
    ],
    "postgresql": [
        "CREATE OR REPLACE FUNCTION novaq_generation_immutable() RETURNS trigger LANGUAGE plpgsql"
        " AS $$BEGIN RETURN NEW; END$$",
    ],
}


def build_state(db: Database, state: str) -> None:
    """Commit a partial schema by running pieces of the repository migration directly."""
    migration = load_migration()
    step = STATES.index(state)
    engine = db.migration_engine()
    try:
        with engine.begin() as connection:
            context = MigrationContext.configure(connection)
            operations = Operations(context)
            with Operations.context(context):
                if state in ("first_column", "partial_backfill"):
                    operations.add_column("datasets", generation_column())
                if state == "partial_backfill":
                    connection.execute(text("UPDATE datasets SET generation = :token WHERE id = 20"), {"token": "a" * 32})
                if step >= STATES.index("datasets_constrained"):
                    migration.upgrade_table("datasets")
                if state == "guards_before_rebuild":
                    # scenarios is backfilled but not constrained, so the upgrade still rebuilds it.
                    operations.add_column("scenarios", generation_column())
                    for row_id in (30, 31, 32):
                        connection.execute(
                            text("UPDATE scenarios SET generation = :token WHERE id = :id"),
                            {"token": new_generation(), "id": row_id},
                        )
                elif step >= STATES.index("both_constrained"):
                    migration.upgrade_table("scenarios")
                if step >= STATES.index("columns_complete"):
                    migration.add_dataset_generation()
                if state in REGISTRY_STATES:
                    migration.create_registry()
                    connection.execute(
                        text(f"INSERT INTO {REGISTRY} (table_name, token, row_id) VALUES (:table, :token, :row_id)"),
                        dict(zip(("table", "token", "row_id"), TOMBSTONE)),
                    )
                if state == "registry_partial":
                    connection.execute(text(
                        f"INSERT INTO {REGISTRY} (table_name, token, row_id) SELECT 'datasets', generation, id FROM datasets"
                    ))
                if step >= STATES.index("registry_backfilled"):
                    migration.backfill_registry()
                if state == "some_guards":
                    for statement in registry_guard_statements(migration, db.dialect):
                        connection.execute(text(statement))
                if step >= STATES.index("guards_before_rebuild"):
                    migration.install_guards()
                if state == "altered_guard":
                    for statement in WEAKENED_GUARD[db.dialect]:
                        connection.execute(text(statement))
    finally:
        engine.dispose()


def registry_guard_statements(migration: ModuleType, dialect: str) -> list[str]:
    """The migration's statements for the registry's own guards (and on PostgreSQL every function)."""
    if dialect == "sqlite":
        return [sql for table, sql in migration.SQLITE_TRIGGERS.values() if table == REGISTRY]
    functions = [migration.PG_FUNCTION_SQL.format(name=name, body=body) for name, body in migration.PG_FUNCTIONS.items()]
    return functions + [sql for table, _function, _tgtype, sql in migration.PG_TRIGGERS.values() if table == REGISTRY]


def generation_column() -> Column[str]:
    """The column as the migration's first step adds it: nullable, no default."""
    return Column("generation", String(32), nullable=True)


@pytest.mark.parametrize("state", STATES)
def test_upgrade_completes_any_partial_state_and_keeps_assigned_tokens(database, monkeypatch, state):
    database.upgrade("0004")
    columns = seed(database)
    build_state(database, state)
    assert database.version() == "0004"
    if state in ("first_column", "partial_backfill"):
        # A backend written before 0005 keeps inserting while the column is half-installed.
        old = MetaData()
        old.reflect(database.engine, only=("datasets",))
        with database.engine.begin() as connection:
            connection.execute(
                insert(old.tables["datasets"]).values(
                    id=90, user_id=1, name="during", source_filename="x.csv", source_format="csv", row_count=0,
                    normalized_json=[], validation_report_json={},
                )
            )
    before = database.digest(columns)
    assigned = {
        table: {row_id: token for row_id, token in database.tokens(table).items() if token is not None}
        for table in IDENTITY_TABLES
        if "generation" in database.columns(table)
    }
    registered = registry_rows(database.engine) if REGISTRY in database.tables() else {}
    fingerprint = schema_fingerprint(database.engine)
    batches = []
    batch_alter_table = Operations.batch_alter_table

    def counting_batch(self, table_name, *args, **kwargs):
        batches.append(table_name)
        return batch_alter_table(self, table_name, *args, **kwargs)

    monkeypatch.setattr(Operations, "batch_alter_table", counting_batch)
    database.upgrade("head")
    assert_complete(database)
    for table, tokens in assigned.items():
        now = database.tokens(table)
        assert all(now[row_id] == token for row_id, token in tokens.items())
    if state == "partial_backfill":
        assert database.tokens("datasets")[20] == "a" * 32
    if state in ("first_column", "partial_backfill"):
        assert TOKEN.match(database.tokens("datasets")[90] or "")
    # Every registration made before the upgrade is kept, the tombstone included; nothing else is added.
    registry = registry_rows(database.engine)
    assert all(registry.get(key) == row_id for key, row_id in registered.items())
    tombstone = {TOMBSTONE[:2]: TOMBSTONE[2]} if state in REGISTRY_STATES else {}
    assert registry == live_registrations(database) | tombstone
    assert batches == EXPECTED_BATCHES[state]
    if state == "complete_unrecorded":
        assert schema_fingerprint(database.engine) == fingerprint
    if state == "altered_guard":
        with pytest.raises(IntegrityError, match=IMMUTABLE):
            database.execute("UPDATE datasets SET generation = :token WHERE id = 20", token=new_generation())
    assert database.digest(columns) == before
    assert database.dataset_generations() == [None, None, None]
    tokens = {table: database.tokens(table) for table in IDENTITY_TABLES}
    database.upgrade("head")
    assert {table: database.tokens(table) for table in IDENTITY_TABLES} == tokens


@pytest.mark.parametrize("table", IDENTITY_TABLES)
def test_duplicate_tokens_are_refused_and_never_replaced(database, table):
    database.upgrade("0004")
    seed(database)
    with database.engine.begin() as connection:
        context = MigrationContext.configure(connection)
        Operations(context).add_column(table, generation_column())
        connection.execute(text(f"UPDATE {table} SET generation = :token"), {"token": "d" * 32})
    for _attempt in range(2):
        with pytest.raises(RuntimeError, match="share a generation token") as raised:
            database.upgrade("head")
        assert ("[20, 21, 22]" if table == "datasets" else "[30, 31, 32]") in str(raised.value)
        assert database.version() == "0004"
        assert set(database.tokens(table).values()) == {"d" * 32}
        assert f"uq_{table}_generation" not in database.unique_names(table)
        assert_no_hardening(database)


CONFLICTS = {
    # The registry says a live token was issued to another row.
    "registered_to_another_row": r"records live datasets tokens as issued to other rows \[\(20, 21\)\]",
    # A registry table without its key or check, holding the same registration twice.
    "malformed_registry": r"exists with an unexpected structure \(generation_registry is not keyed by",
}


def build_conflict(db: Database, conflict: str) -> None:
    build_state(db, "columns_complete")
    engine = db.migration_engine()
    try:
        with engine.begin() as connection:
            token = connection.execute(text("SELECT generation FROM datasets WHERE id = 20")).scalar()
            if conflict == "registered_to_another_row":
                with Operations.context(MigrationContext.configure(connection)):
                    load_migration().create_registry()
                rows = [(token, 21)]
            else:
                connection.execute(text(
                    f"CREATE TABLE {REGISTRY} (table_name VARCHAR(32) NOT NULL, token VARCHAR(32) NOT NULL,"
                    " row_id INTEGER NOT NULL, registered_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP)"
                ))
                rows = [(token, 20), (token, 20)]
            for registered, row_id in rows:
                connection.execute(
                    text(f"INSERT INTO {REGISTRY} (table_name, token, row_id) VALUES ('datasets', :token, :row_id)"),
                    {"token": registered, "row_id": row_id},
                )
    finally:
        engine.dispose()


@pytest.mark.parametrize("conflict", CONFLICTS)
def test_conflicting_registry_state_stops_the_upgrade_and_is_never_rewritten(database, conflict):
    database.upgrade("0004")
    seed(database)
    build_conflict(database, conflict)
    tokens = {table: database.tokens(table) for table in IDENTITY_TABLES}
    fingerprint = schema_fingerprint(database.engine)
    for _attempt in range(2):
        with pytest.raises(RuntimeError, match=CONFLICTS[conflict]):
            database.upgrade("head")
        assert database.version() == "0004"
        assert {table: database.tokens(table) for table in IDENTITY_TABLES} == tokens
        assert schema_fingerprint(database.engine) == fingerprint
        assert guard_catalog(database.engine) == empty_catalog(database.dialect)


def test_rerunning_the_registry_steps_adds_and_replaces_nothing(database):
    database.upgrade("0004")
    seed(database)
    database.upgrade("head")
    database.execute("DELETE FROM scenarios WHERE id = 32")
    registry = registry_rows(database.engine)
    fingerprint = schema_fingerprint(database.engine)
    migration = load_migration()
    engine = database.migration_engine()
    try:
        for _attempt in range(2):
            with engine.begin() as connection:
                with Operations.context(MigrationContext.configure(connection)):
                    migration.create_registry()
                    migration.backfill_registry()
                    migration.install_guards()
                    migration.assert_postconditions()
    finally:
        engine.dispose()
    assert registry_rows(database.engine) == registry
    assert schema_fingerprint(database.engine) == fingerprint


def test_sqlite_leftover_rebuild_copy_is_cleared_only_when_the_original_survives(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "")
    db = Database(f"sqlite:///{(tmp_path / 'leftover.db').as_posix()}", "sqlite")
    try:
        db.upgrade("0004")
        seed(db)
        db.execute("CREATE TABLE _alembic_tmp_datasets AS SELECT * FROM datasets")
        db.upgrade("head")
        assert_complete(db)
    finally:
        db.engine.dispose()


def test_sqlite_leftover_rebuild_copy_is_kept_when_the_original_is_missing(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "")
    db = Database(f"sqlite:///{(tmp_path / 'lost.db').as_posix()}", "sqlite")
    event.remove(db.engine, "connect", _enforce_sqlite_foreign_keys)
    try:
        db.upgrade("0004")
        seed(db)
        db.execute("CREATE TABLE _alembic_tmp_datasets AS SELECT * FROM datasets")
        db.execute("DROP TABLE datasets")
        with pytest.raises(RuntimeError, match="may hold the only copy"):
            db.upgrade("head")
        assert db.version() == "0004"
        with db.engine.connect() as connection:
            assert connection.execute(text("SELECT count(*) FROM _alembic_tmp_datasets")).scalar() == 3
    finally:
        db.engine.dispose()


def test_postconditions_refuse_to_record_0005_over_an_incomplete_schema(database):
    database.upgrade("0004")
    seed(database)
    migration = load_migration()
    engine = database.migration_engine()
    try:
        with engine.begin() as connection:
            with Operations.context(MigrationContext.configure(connection)):
                migration.upgrade_table("datasets")
                with pytest.raises(RuntimeError, match="scenarios.generation is missing"):
                    migration.assert_postconditions()
    finally:
        engine.dispose()
    assert database.version() == "0004"


# --- the installed guards -----------------------------------------------------------------------


def test_final_head_has_exactly_the_defined_guards_installed_after_the_last_rebuild(database, monkeypatch):
    database.upgrade("0004")
    seed(database)
    steps: list[str] = []
    batch_alter_table, execute = Operations.batch_alter_table, Operations.execute

    def recording_batch(self, table_name, *args, **kwargs):
        steps.append(f"rebuild {table_name}")
        return batch_alter_table(self, table_name, *args, **kwargs)

    def recording_execute(self, sqltext, *args, **kwargs):
        if str(sqltext).startswith("CREATE TRIGGER"):
            steps.append(f"trigger {str(sqltext).split()[2]}")
        return execute(self, sqltext, *args, **kwargs)

    monkeypatch.setattr(Operations, "batch_alter_table", recording_batch)
    monkeypatch.setattr(Operations, "execute", recording_execute)
    database.upgrade("head")
    rebuilds = [index for index, step in enumerate(steps) if step.startswith("rebuild")]
    triggers = [step.split()[1] for step in steps if step.startswith("trigger")]
    assert [steps[index] for index in rebuilds] == ["rebuild datasets", "rebuild scenarios"]
    assert steps[: rebuilds[-1] + 1] == ["rebuild datasets", "rebuild scenarios"]
    trigger_names = guards.SQLITE_TRIGGERS if database.dialect == "sqlite" else guards.PG_TRIGGERS
    assert triggers == list(trigger_names)
    assert guard_catalog(database.engine) == expected_catalog(database.dialect)
    assert registry_rows(database.engine) == live_registrations(database)


@pytest.mark.parametrize("table", IDENTITY_TABLES)
def test_an_update_that_keeps_the_token_is_allowed(guarded, table):
    tokens = guarded.tokens(table)
    registry = registry_rows(guarded.engine)
    guarded.execute(f"UPDATE {table} SET name = 'renamed', generation = generation")
    first = min(tokens)
    guarded.execute(f"UPDATE {table} SET name = 'again', generation = :token WHERE id = :id", token=tokens[first], id=first)
    with make_sessionmaker(guarded.engine)() as session:
        record = session.get(MODELS[table], first)
        record.name = "orm"
        record.generation = tokens[first]
        session.commit()
    with guarded.engine.connect() as connection:
        names = dict(connection.execute(text(f"SELECT id, name FROM {table}")).all())
    assert names == {row_id: "orm" if row_id == first else "renamed" for row_id in tokens}
    assert guarded.tokens(table) == tokens
    assert registry_rows(guarded.engine) == registry


@pytest.mark.parametrize("table", IDENTITY_TABLES)
def test_reassigning_a_token_is_refused(guarded, table):
    tokens = guarded.tokens(table)
    first, last = min(tokens), max(tokens)
    for value in (new_generation(), tokens[last], None):
        with pytest.raises(IntegrityError, match=IMMUTABLE):
            guarded.execute(f"UPDATE {table} SET generation = :token WHERE id = :id", token=value, id=first)
    with pytest.raises(IntegrityError, match=IMMUTABLE):
        guarded.execute(f"UPDATE {table} SET generation = :token", token=new_generation())
    assert guarded.tokens(table) == tokens


def test_orm_reassignment_is_refused(guarded):
    tokens = {table: guarded.tokens(table) for table in IDENTITY_TABLES}
    session_factory = make_sessionmaker(guarded.engine)
    for table, row_id in (("datasets", 20), ("scenarios", 30)):
        with session_factory() as session:
            record = session.get(MODELS[table], row_id)
            record.generation = new_generation()
            with pytest.raises(IntegrityError, match=IMMUTABLE):
                session.commit()
    assert {table: guarded.tokens(table) for table in IDENTITY_TABLES} == tokens


@pytest.mark.parametrize("table", IDENTITY_TABLES)
def test_a_deleted_token_is_never_reissued(guarded, table):
    row_id = RETIRED[table]
    token = guarded.tokens(table)[row_id]
    guarded.execute(f"DELETE FROM {table} WHERE id = :id", id=row_id)
    with pytest.raises(IntegrityError, match=REUSE):
        insert_row(guarded, table, 500, token)
    with pytest.raises(IntegrityError, match=REUSE):
        with guarded.engine.begin() as connection:
            connection.execute(
                insert(Base.metadata.tables[table]).values(
                    id=501, user_id=1, name="again", generation=token, **MODEL_REQUIRED[table]
                )
            )
    assert not {row_id, 500, 501} & set(guarded.tokens(table))
    assert registry_rows(guarded.engine)[(table, token)] == row_id


@pytest.mark.parametrize("table", IDENTITY_TABLES)
def test_a_reused_id_gets_a_fresh_token(guarded, table):
    row_id = RETIRED[table]
    old = guarded.tokens(table)[row_id]
    guarded.execute(f"DELETE FROM {table} WHERE id = :id", id=row_id)
    with make_sessionmaker(guarded.engine)() as session:
        again = MODELS[table](id=row_id, user_id=1, name="reused id", **MODEL_REQUIRED[table])
        session.add(again)
        session.commit()
        fresh = again.generation
    assert TOKEN.match(fresh) and fresh != old
    assert guarded.tokens(table)[row_id] == fresh
    registry = registry_rows(guarded.engine)
    assert registry[(table, old)] == row_id
    assert registry[(table, fresh)] == row_id


@pytest.mark.parametrize("table", IDENTITY_TABLES)
def test_a_reused_id_can_never_take_its_old_token(guarded, table):
    row_id = RETIRED[table]
    old = guarded.tokens(table)[row_id]
    guarded.execute(f"DELETE FROM {table} WHERE id = :id", id=row_id)
    with make_sessionmaker(guarded.engine)() as session:
        session.add(MODELS[table](id=row_id, user_id=1, name="old id, old token", generation=old, **MODEL_REQUIRED[table]))
        with pytest.raises(IntegrityError, match=REUSE):
            session.commit()
    with pytest.raises(IntegrityError, match=REUSE):
        insert_row(guarded, table, row_id, old)
    assert row_id not in guarded.tokens(table)


def test_registry_rows_outlive_every_deleted_record(guarded):
    registry = registry_rows(guarded.engine)
    assert registry == live_registrations(guarded)
    assert len(registry) == 6
    guarded.execute("DELETE FROM scenarios")
    guarded.execute("DELETE FROM datasets")
    assert guarded.tokens("datasets") == {} and guarded.tokens("scenarios") == {}
    assert registry_rows(guarded.engine) == registry


def test_registry_rows_cannot_be_updated_or_deleted(guarded):
    registry = registry_rows(guarded.engine)
    (table, token), _row_id = min(registry.items())
    one = {"table": table, "token": token}
    for statement, params in (
        (f"UPDATE {REGISTRY} SET row_id = row_id + 1000", {}),
        (f"UPDATE {REGISTRY} SET token = :fresh WHERE table_name = :table AND token = :token",
         {**one, "fresh": new_generation()}),
        (f"UPDATE {REGISTRY} SET table_name = 'scenarios' WHERE table_name = 'datasets'", {}),
        (f"DELETE FROM {REGISTRY} WHERE table_name = :table AND token = :token", one),
        (f"DELETE FROM {REGISTRY}", {}),
    ):
        with pytest.raises(IntegrityError, match=APPEND_ONLY):
            guarded.execute(statement, **params)
    assert registry_rows(guarded.engine) == registry


def test_postgresql_registry_cannot_be_truncated(postgres_guarded):
    db = postgres_guarded
    registry = registry_rows(db.engine)
    for statement in (
        f"TRUNCATE {REGISTRY}",
        f"TRUNCATE {REGISTRY} CASCADE",
        f"TRUNCATE datasets, scenarios, {REGISTRY}",
    ):
        with pytest.raises(IntegrityError, match=APPEND_ONLY):
            db.execute(statement)
    assert registry_rows(db.engine) == registry
    assert len(db.tokens("datasets")) == 3
    # Truncating a source table removes rows without deleting row by row; their tokens stay issued.
    truncated = db.tokens("scenarios")
    db.execute("TRUNCATE scenarios")
    assert registry_rows(db.engine) == registry
    with pytest.raises(IntegrityError, match=REUSE):
        insert_row(db, "scenarios", 30, truncated[30])


def test_sqlite_conflict_clauses_cannot_bypass_the_guards(sqlite_guarded):
    db = sqlite_guarded
    retired = db.tokens("scenarios")[32]
    db.execute("DELETE FROM scenarios WHERE id = 32")
    live = db.tokens("datasets")
    registry = registry_rows(db.engine)
    fresh = new_generation()
    # A deleted token cannot come back through any conflict clause.
    for verb, suffix in (
        ("INSERT OR IGNORE", ""),
        ("INSERT OR REPLACE", ""),
        ("REPLACE", ""),
        ("INSERT OR ROLLBACK", ""),
        ("INSERT OR FAIL", ""),
        ("INSERT", " ON CONFLICT DO NOTHING"),
        ("INSERT", " ON CONFLICT(id) DO UPDATE SET name = excluded.name"),
    ):
        with pytest.raises(IntegrityError, match=REUSE):
            insert_row(db, "scenarios", 32, retired, verb=verb, suffix=suffix)
    # Replacing a live row re-inserts it, which would reissue its token.
    for verb in ("INSERT OR REPLACE", "REPLACE"):
        with pytest.raises(IntegrityError, match=REUSE):
            insert_row(db, "datasets", 22, live[22], verb=verb)
    # OR IGNORE against a live row skips the insert and changes nothing.
    insert_row(db, "datasets", 22, live[22], verb="INSERT OR IGNORE")
    # An upsert or an UPDATE with a conflict clause cannot change a token.
    with pytest.raises(IntegrityError, match=IMMUTABLE):
        insert_row(db, "datasets", 20, fresh, suffix=" ON CONFLICT(id) DO UPDATE SET generation = excluded.generation")
    for verb in ("UPDATE OR REPLACE", "UPDATE OR IGNORE", "UPDATE OR ROLLBACK", "UPDATE OR FAIL"):
        for value in (fresh, live[21]):
            with pytest.raises(IntegrityError, match=IMMUTABLE):
                db.execute(f"{verb} datasets SET generation = :token WHERE id = 20", token=value)
    # The registry itself cannot be overwritten, updated or deleted through a conflict clause.
    for verb in ("INSERT OR REPLACE", "INSERT OR IGNORE", "REPLACE", "INSERT OR FAIL"):
        with pytest.raises(IntegrityError, match=REUSE):
            db.execute(
                f"{verb} INTO {REGISTRY} (table_name, token, row_id) VALUES ('scenarios', :token, 999)", token=retired
            )
    for verb in ("UPDATE OR REPLACE", "UPDATE OR IGNORE"):
        with pytest.raises(IntegrityError, match=APPEND_ONLY):
            db.execute(f"{verb} {REGISTRY} SET row_id = 999")
    assert db.tokens("datasets") == live
    assert 32 not in db.tokens("scenarios")
    with db.engine.connect() as connection:
        assert connection.execute(text("SELECT name FROM datasets WHERE id = 22")).scalar() == "dataset 2"
    assert registry_rows(db.engine) == registry


def test_postgresql_on_conflict_cannot_bypass_the_guards(postgres_guarded):
    db = postgres_guarded
    retired = db.tokens("scenarios")[32]
    db.execute("DELETE FROM scenarios WHERE id = 32")
    live = db.tokens("datasets")
    registry = registry_rows(db.engine)
    for suffix in (" ON CONFLICT DO NOTHING", " ON CONFLICT (id) DO UPDATE SET name = EXCLUDED.name"):
        with pytest.raises(IntegrityError, match=REUSE):
            insert_row(db, "scenarios", 32, retired, suffix=suffix)
    for suffix in (
        " ON CONFLICT (id) DO UPDATE SET generation = EXCLUDED.generation",
        " ON CONFLICT (id) DO UPDATE SET generation = NULL",
    ):
        with pytest.raises(IntegrityError, match=IMMUTABLE):
            insert_row(db, "datasets", 20, new_generation(), suffix=suffix)
    with pytest.raises(IntegrityError, match=APPEND_ONLY):
        db.execute(
            f"INSERT INTO {REGISTRY} (table_name, token, row_id) VALUES ('scenarios', :token, 999)"
            " ON CONFLICT (table_name, token) DO UPDATE SET row_id = EXCLUDED.row_id",
            token=retired,
        )
    # DO NOTHING on the registry only skips the insert; the registration is unchanged.
    db.execute(
        f"INSERT INTO {REGISTRY} (table_name, token, row_id) VALUES ('scenarios', :token, 999) ON CONFLICT DO NOTHING",
        token=retired,
    )
    assert db.tokens("datasets") == live
    assert 32 not in db.tokens("scenarios")
    assert registry_rows(db.engine) == registry


def test_orm_inserts_are_registered(guarded):
    with make_sessionmaker(guarded.engine)() as session:
        dataset = Dataset(user_id=1, name="orm", source_filename="o.csv", source_format="csv")
        session.add(dataset)
        session.flush()
        scenario = Scenario(user_id=1, dataset_id=dataset.id, name="orm")
        session.add(scenario)
        session.commit()
        added = {("datasets", dataset.generation): dataset.id, ("scenarios", scenario.generation): scenario.id}
    registry = registry_rows(guarded.engine)
    assert {key: registry.get(key) for key in added} == added
    assert registry == live_registrations(guarded)


def test_direct_sql_inserts_are_registered(guarded):
    insert_row(guarded, "datasets", 210, new_generation())
    insert_row(guarded, "scenarios", 310, new_generation())
    if guarded.build == "migrated":
        # The migration's database default assigns the token, and the insert registers it.
        guarded.execute(
            "INSERT INTO scenarios (id, user_id, name, settings_json, results_json) VALUES (311, 1, 'raw', '{}', '{}')"
        )
        assert TOKEN.match(guarded.tokens("scenarios")[311] or "")
    registry = registry_rows(guarded.engine)
    assert registry == live_registrations(guarded)
    assert registry[("datasets", guarded.tokens("datasets")[210] or "")] == 210


def test_a_dataset_and_a_scenario_may_hold_the_same_token(guarded):
    token = new_generation()
    insert_row(guarded, "datasets", 200, token)
    insert_row(guarded, "scenarios", 300, token)
    registry = registry_rows(guarded.engine)
    assert registry[("datasets", token)] == 200
    assert registry[("scenarios", token)] == 300
    # A token one table issued and deleted can still be issued by the other table.
    retired = guarded.tokens("scenarios")[32]
    guarded.execute("DELETE FROM scenarios WHERE id = 32")
    insert_row(guarded, "datasets", 201, retired)
    registry = registry_rows(guarded.engine)
    assert registry[("scenarios", retired)] == 32
    assert registry[("datasets", retired)] == 201


@pytest.mark.parametrize("table", IDENTITY_TABLES)
def test_a_token_is_unique_within_its_table(guarded, table):
    tokens = guarded.tokens(table)
    registry = registry_rows(guarded.engine)
    with pytest.raises(IntegrityError, match=rf"uq_{table}_generation|UNIQUE constraint failed: {table}\.generation"):
        insert_row(guarded, table, 400, tokens[min(tokens)])
    assert guarded.tokens(table) == tokens
    assert registry_rows(guarded.engine) == registry


# --- create_all ---------------------------------------------------------------------------------


@pytest.mark.parametrize("dialect", DIALECTS)
def test_create_all_builds_the_same_registry_and_guards_as_the_migration(dialect, tmp_path, monkeypatch):
    with (
        open_database(dialect, tmp_path / "migrated", monkeypatch) as migrated,
        open_database(dialect, tmp_path / "built", monkeypatch) as built,
    ):
        migrated.upgrade("head")
        Base.metadata.create_all(built.engine)
        assert guard_catalog(built.engine) == guard_catalog(migrated.engine) == expected_catalog(dialect)
        assert registry_structure(built) == registry_structure(migrated)


def test_create_all_refuses_to_add_the_registry_to_pre_0005_tables(database):
    database.upgrade("0004")
    seed(database)
    fingerprint = schema_fingerprint(database.engine)
    with pytest.raises(RuntimeError, match=r"Run migration 0005 \(alembic upgrade head\)"):
        Base.metadata.create_all(database.engine)
    assert database.version() == "0004"
    assert_no_hardening(database)
    assert schema_fingerprint(database.engine) == fingerprint


def test_create_all_and_seed_user_leave_a_migrated_database_unchanged(database, monkeypatch):
    database.upgrade("0004")
    seed(database)
    database.upgrade("head")
    if database.dialect == "postgresql":
        # The seed chose its ids; a real database would have drawn them from the sequence.
        database.execute("SELECT setval(pg_get_serial_sequence('users', 'id'), (SELECT max(id) FROM users))")
    fingerprint = schema_fingerprint(database.engine)
    Base.metadata.create_all(database.engine)
    monkeypatch.delenv("NOVAQ_ENV", raising=False)
    monkeypatch.setattr(bootstrap, "get_engine", lambda: database.engine)
    assert bootstrap.seed_user("bootstrap@example.com", "admin123") == "created"
    assert schema_fingerprint(database.engine) == fingerprint
    assert_complete(database)


def test_create_all_guards_work_in_the_suite_schema(db_engine):
    """The schema the rest of the suite uses: a per-test PostgreSQL schema when NOVAQ_TEST_DATABASE_URL is set."""
    assert guard_catalog(db_engine) == expected_catalog(db_engine.dialect.name)
    user = create_user(db_engine, "guards@example.com", "pw")
    session_factory = make_sessionmaker(db_engine)
    with session_factory() as session:
        dataset = Dataset(user_id=user.id, name="d", source_filename="d.csv", source_format="csv")
        session.add(dataset)
        session.commit()
        token, row_id = dataset.generation, dataset.id
        assert registry_rows(db_engine) == {("datasets", token): row_id}
        dataset.generation = new_generation()
        with pytest.raises(IntegrityError, match=IMMUTABLE):
            session.commit()
    with session_factory() as session:
        session.delete(session.get(Dataset, row_id))
        session.commit()
        session.add(Dataset(user_id=user.id, name="again", source_filename="d.csv", source_format="csv", generation=token))
        with pytest.raises(IntegrityError, match=REUSE):
            session.commit()
    assert registry_rows(db_engine) == {("datasets", token): row_id}


# --- downgrade and the jobs table -----------------------------------------------------------------


def test_downgrade_removes_every_guard_and_the_registry_then_upgrade_installs_a_fresh_set(database):
    """Downgrade is rehearsal only, and it destroys the record of issued tokens (see the migration)."""
    database.upgrade("0004")
    seed(database)
    tables_0004 = database.tables()
    schema_0004 = {table: database.schema(table) for table in tables_0004}
    database.upgrade("head")
    retired = database.tokens("scenarios")[32]
    database.execute("DELETE FROM scenarios WHERE id = 32")
    database.downgrade("0004")
    assert database.version() == "0004"
    assert_no_hardening(database)
    assert database.tables() == tables_0004
    assert {table: database.schema(table) for table in tables_0004} == schema_0004
    if database.dialect == "sqlite":
        with database.engine.connect() as connection:
            assert connection.execute(text("PRAGMA integrity_check")).scalar() == "ok"
            assert connection.execute(text("PRAGMA foreign_key_check")).all() == []
    database.upgrade("head")
    assert_complete(database)
    assert registry_rows(database.engine) == live_registrations(database)
    # The documented cost of a downgrade: the registry that refused this token is gone.
    insert_row(database, "scenarios", 32, retired)
    assert registry_rows(database.engine)[("scenarios", retired)] == 32


def test_historical_jobs_are_byte_for_byte_unchanged(database, monkeypatch):
    database.upgrade("0004")
    seed(database)
    jobs = job_rows(database)
    columns = set(database.columns("jobs"))
    upgrade_with_fault(database, monkeypatch, "after_registry_backfill")
    assert job_rows(database) == jobs
    database.upgrade("head")
    assert job_rows(database) == jobs
    assert set(database.columns("jobs")) == columns
    database.downgrade("0004")
    assert job_rows(database) == jobs


# --- backup and restore -------------------------------------------------------------------------


def test_restoring_a_pre_0005_backup_then_migrating_assigns_new_identities(database):
    database.upgrade("0004")
    columns = seed(database)
    backup = database.copy("pre_0005")
    database.upgrade("head")
    original = {table: database.tokens(table) for table in IDENTITY_TABLES}
    backup.upgrade("head")
    assert_complete(backup)
    assert backup.digest(columns) == database.digest(columns)
    for table in IDENTITY_TABLES:
        assert set(original[table].values()).isdisjoint(backup.tokens(table).values())
    assert set(registry_rows(database.engine)).isdisjoint(registry_rows(backup.engine))
    # Jobs carry no generation token, before or after, on either copy.
    assert set(backup.columns("jobs")) == set(columns["jobs"])
    with backup.engine.connect() as connection:
        params = connection.execute(text("SELECT params_json FROM jobs ORDER BY id")).scalars().all()
    assert all("generation" not in str(value) for value in params)


def test_restoring_a_post_0005_backup_keeps_its_tokens(database):
    database.upgrade("0004")
    seed(database)
    database.upgrade("head")
    retired = database.tokens("scenarios")[32]
    database.execute("DELETE FROM scenarios WHERE id = 32")
    original = {table: database.tokens(table) for table in IDENTITY_TABLES}
    registry = registry_rows(database.engine)
    backup = database.copy("post_0005")
    assert backup.version() == "0005"
    assert {table: backup.tokens(table) for table in IDENTITY_TABLES} == original
    assert registry_rows(backup.engine) == registry
    assert guard_catalog(backup.engine) == expected_catalog(backup.dialect)
    backup.upgrade("head")
    assert {table: backup.tokens(table) for table in IDENTITY_TABLES} == original
    assert_complete(backup)
    with pytest.raises(IntegrityError, match=REUSE):
        insert_row(backup, "scenarios", 32, retired)
    assert registry_rows(backup.engine) == registry


# --- the model fields and the two copies of the guards ------------------------------------------


def test_model_declares_the_generation_columns():
    for model, table in ((Dataset, "datasets"), (Scenario, "scenarios")):
        column = model.__table__.c.generation
        assert column.nullable is False
        assert column.server_default is None
        assert column.default is not None and column.default.arg.__name__ == new_generation.__name__
        assert any(
            getattr(constraint, "name", None) == f"uq_{table}_generation" for constraint in model.__table__.constraints
        )
    binding = Scenario.__table__.c.dataset_generation
    assert binding.nullable is True
    assert binding.default is None and binding.server_default is None
    assert not {"generation", "dataset_generation"} & set(Job.__table__.c.keys())
    assert TOKEN.match(new_generation())
    registry = Base.metadata.tables[REGISTRY]
    assert [column.name for column in registry.primary_key.columns] == ["table_name", "token"]
    assert not registry.foreign_keys
    assert not any(column.nullable for column in registry.columns)
    order = [table.name for table in Base.metadata.sorted_tables]
    assert order.index(REGISTRY) > max(order.index(table) for table in IDENTITY_TABLES)


def test_migration_and_application_declare_identical_guards():
    migration = load_migration()
    for name in ("TABLES", "REGISTRY", "SQLITE_TRIGGERS", "PG_FUNCTION_SQL", "PG_FUNCTIONS", "PG_TRIGGERS"):
        assert getattr(migration, name) == getattr(guards, name), name
    for dialect in (sqlite.dialect(), postgresql.dialect()):
        migrated = CreateTable(Table(REGISTRY, MetaData(), *migration.registry_elements())).compile(dialect=dialect)
        declared = CreateTable(Base.metadata.tables[REGISTRY]).compile(dialect=dialect)
        assert str(migrated) == str(declared)
    assert list(migration.REGISTRY_COLUMNS) == list(Base.metadata.tables[REGISTRY].c.keys())


def test_migration_imports_no_application_code():
    imported: set[str] = set()
    for node in ast.walk(ast.parse(MIGRATION_FILE.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            imported |= {alias.name.split(".")[0] for alias in node.names}
        elif isinstance(node, ast.ImportFrom):
            imported.add((node.module or "").split(".")[0])
    assert imported == {"__future__", "collections", "typing", "sqlalchemy", "alembic"}


def test_no_api_or_report_code_reads_the_registry():
    sources = [path for folder in ("api", "reports") for path in (REPO_ROOT / "backend" / folder).rglob("*.py")]
    assert sources
    assert [path for path in sources if re.search(r"generation_registry|generation_guards", path.read_text(encoding="utf-8"))] == []


# --- the model fields on the create_all schema --------------------------------------------------


def test_orm_assigns_distinct_tokens_and_rejects_duplicates(db_engine):
    user = create_user(db_engine, "orm@example.com", "pw")
    session_factory = make_sessionmaker(db_engine)
    with session_factory() as session:
        dataset = Dataset(user_id=user.id, name="d", source_filename="d.csv", source_format="csv")
        session.add(dataset)
        session.flush()
        scenario = Scenario(user_id=user.id, dataset_id=dataset.id, name="s")
        session.add(scenario)
        session.commit()
        assert TOKEN.match(dataset.generation) and TOKEN.match(scenario.generation)
        assert dataset.generation != scenario.generation
        assert scenario.dataset_generation is None
    with session_factory() as session:
        session.add_all(
            [Dataset(user_id=user.id, name=name, source_filename="d.csv", source_format="csv", generation="a" * 32)
             for name in ("first", "second")]
        )
        with pytest.raises(IntegrityError):
            session.commit()


def test_replacement_with_same_id_and_created_at_gets_a_new_token(db_engine):
    user = create_user(db_engine, "reuse@example.com", "pw")
    session_factory = make_sessionmaker(db_engine)
    created_at = datetime(2026, 9, 1, 8, 0, tzinfo=timezone.utc)
    with session_factory() as session:
        first = Dataset(
            id=500, user_id=user.id, name="same", source_filename="d.csv", source_format="csv", created_at=created_at
        )
        session.add(first)
        session.commit()
        token = first.generation
        session.delete(first)
        session.commit()
        second = Dataset(
            id=500, user_id=user.id, name="same", source_filename="d.csv", source_format="csv", created_at=created_at
        )
        session.add(second)
        session.commit()
        assert second.id == 500 and second.generation != token


def test_dataset_and_scenario_deletion_are_unchanged(db_engine):
    user = create_user(db_engine, "delete@example.com", "pw")
    session_factory = make_sessionmaker(db_engine)
    with session_factory() as session:
        dataset = Dataset(user_id=user.id, name="d", source_filename="d.csv", source_format="csv")
        session.add(dataset)
        session.flush()
        kept, removed = (Scenario(user_id=user.id, dataset_id=dataset.id, name=name) for name in ("kept", "removed"))
        session.add_all([kept, removed])
        session.commit()
        session.delete(removed)
        session.commit()
        assert session.get(Dataset, dataset.id) is not None
        session.delete(dataset)
        session.commit()
        assert session.execute(select(Scenario)).scalars().all() == []
