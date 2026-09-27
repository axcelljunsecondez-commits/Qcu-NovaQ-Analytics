"""Generation identity (migration 0005 and the model fields): backfill, defaults, recovery and restore.

Spec: docs/superpowers/specs/2026-09-26-generation-identity-contract.md.

Every ``database`` test runs the real migration chain on SQLite. The ``postgresql`` variants run only
when NOVAQ_TEST_DATABASE_URL names a dedicated database ending in _test; each variant creates and
drops its own database. Tests that use ``db_engine`` run on the ``create_all`` schema instead.
"""

from __future__ import annotations

import importlib.util
import json
import os
import re
import shutil
import uuid
from collections.abc import Iterator
from datetime import datetime, timezone
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest
from alembic import command
from alembic.config import Config
from alembic.ddl.impl import DefaultImpl
from alembic.operations import BatchOperations, Operations
from alembic.runtime.migration import MigrationContext
from fastapi.testclient import TestClient
from sqlalchemy import Column, MetaData, String, create_engine, event, insert, inspect, select, text
from sqlalchemy.engine import Engine, make_url
from sqlalchemy.exc import DBAPIError, IntegrityError

from backend.api.email_delivery import FakeEmailSender
from backend.api.main import create_app
from backend.api.settings import Settings
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


class Database:
    """A disposable database driven through the repository's Alembic chain."""

    def __init__(self, url: str, dialect: str, admin: Engine | None = None) -> None:
        self.url = url
        self.dialect = dialect
        self.admin = admin
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


@pytest.fixture(params=["sqlite", "postgresql"])
def database(request, tmp_path, monkeypatch) -> Iterator[Database]:
    monkeypatch.setenv("DATABASE_URL", "")
    admin: Engine | None = None
    if request.param == "sqlite":
        first = Database(f"sqlite:///{(tmp_path / 'generation.db').as_posix()}", "sqlite")
    else:
        source = os.environ.get("NOVAQ_TEST_DATABASE_URL")
        if not source:
            pytest.skip("NOVAQ_TEST_DATABASE_URL is required for the PostgreSQL variant")
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

    monkeypatch.setattr(Database, "copy", tracked_copy)
    try:
        yield first
    finally:
        for db in created:
            db.drop()
        if admin is not None:
            admin.dispose()


def load_migration() -> ModuleType:
    spec = importlib.util.spec_from_file_location("migration_0005_under_test", MIGRATION_FILE)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def seed(db: Database) -> dict[str, list[str]]:
    """Insert rows at the current revision through tables reflected from it; return their columns."""
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


def assert_untouched(db: Database, before: dict[str, dict[str, Any]]) -> None:
    assert db.version() == "0004"
    for table in IDENTITY_TABLES:
        assert db.schema(table) == before[table]


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


def test_application_on_the_migrated_schema_assigns_and_hides_tokens(database, monkeypatch):
    database.upgrade("head")
    engine = create_engine_for(database.url)
    try:
        client = TestClient(create_app(engine=engine, settings=Settings(), email_sender=FakeEmailSender()))
        create_user(engine, "g@example.com", "pw")
        assert login(client, "g@example.com", "pw") == 200
        supplied = {"generation": "f" * 32, "dataset_generation": "e" * 32}
        body = {"name": "Morning rush", "settings": {"target_utilization": 0.7}, "results": {"segments": 4}}
        created = client.post("/scenarios", headers=csrf_header(client), json={**body, **supplied})
        assert created.status_code == 201
        scenario = created.json()["scenario"]
        assert not set(supplied) & set(scenario)
        stored = database.tokens("scenarios")[scenario["id"]]
        assert stored is not None and TOKEN.match(stored) and stored != supplied["generation"]
        assert database.dataset_generations() == [None]
        patched = client.patch(
            f"/scenarios/{scenario['id']}", headers=csrf_header(client), json={"name": "Renamed", **supplied}
        )
        assert patched.status_code == 200
        assert database.tokens("scenarios")[scenario["id"]] == stored
        assert database.dataset_generations() == [None]
        uploaded = client.post(
            "/datasets", headers=csrf_header(client), files={"file": ("d.csv", CSV_GOOD, "application/octet-stream")}
        )
        assert uploaded.status_code == 201
        dataset = uploaded.json()["dataset"]
        assert "generation" not in dataset
        assert TOKEN.match(database.tokens("datasets")[dataset["id"]] or "")
        assert "generation" not in client.get(f"/datasets/{dataset['id']}").json()["dataset"]
        assert client.delete(f"/scenarios/{scenario['id']}", headers=csrf_header(client)).status_code == 200
        assert client.delete(f"/datasets/{dataset['id']}", headers=csrf_header(client)).status_code == 200
        assert database.tokens("scenarios") == {}
        assert database.tokens("datasets") == {}
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
)


def upgrade_with_fault(db: Database, monkeypatch, fault: str) -> BaseException:
    """Run the unmodified migration with one fault injected into Alembic from outside it."""
    add_column, execute = Operations.add_column, Operations.execute
    create_unique = BatchOperations.create_unique_constraint
    rename_table, add_constraint = DefaultImpl.rename_table, DefaultImpl.add_constraint

    def faulty_add_column(self, table_name, column, *args, **kwargs):
        if (
            fault == "before_any_change"
            or (fault == "after_datasets_constraint" and table_name == "scenarios")
            or (fault == "after_both_constraints" and column.name == "dataset_generation")
        ):
            raise InjectedFault(fault)
        return add_column(self, table_name, column, *args, **kwargs)

    def faulty_execute(self, sqltext, *args, **kwargs):
        backfill = str(sqltext).startswith("UPDATE datasets")
        if fault == "after_first_column" and backfill:
            raise InjectedFault(fault)
        result = execute(self, sqltext, *args, **kwargs)
        if fault == "during_backfill" and backfill:
            raise InjectedFault(fault)
        return result

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
    if fault == "silent_missing_constraint":
        assert "scenarios.generation has no unique constraint" in str(error)
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
    assert database.digest(columns) == before
    assert database.dataset_generations() == [None, None, None]
    tokens = {table: database.tokens(table) for table in IDENTITY_TABLES}
    database.upgrade("head")
    assert {table: database.tokens(table) for table in IDENTITY_TABLES} == tokens


def test_repeated_failures_then_success_assign_each_token_once(database, monkeypatch):
    database.upgrade("0004")
    columns = seed(database)
    before = database.digest(columns)
    for fault in ("after_first_column", "after_first_column", "during_backfill", "after_both_constraints"):
        upgrade_with_fault(database, monkeypatch, fault)
        assert database.version() == "0004"
    database.upgrade("head")
    assert_complete(database)
    assert database.digest(columns) == before


def build_state(db: Database, state: str) -> None:
    """Commit a partial schema by running pieces of the repository migration directly."""
    migration = load_migration()
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
                if state in ("datasets_constrained", "both_constrained", "complete_unrecorded"):
                    migration.upgrade_table("datasets")
                if state in ("both_constrained", "complete_unrecorded"):
                    migration.upgrade_table("scenarios")
                if state == "complete_unrecorded":
                    migration.add_dataset_generation()
    finally:
        engine.dispose()


def generation_column() -> Column[str]:
    """The column as the migration's first step adds it: nullable, no default."""
    return Column("generation", String(32), nullable=True)


@pytest.mark.parametrize(
    "state", ["first_column", "partial_backfill", "datasets_constrained", "both_constrained", "complete_unrecorded"]
)
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
    expected_batches = {
        "first_column": ["datasets", "scenarios"],
        "partial_backfill": ["datasets", "scenarios"],
        "datasets_constrained": ["scenarios"],
        "both_constrained": [],
        "complete_unrecorded": [],
    }
    assert batches == expected_batches[state]
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
    # Jobs carry no generation token, before or after, on either copy.
    assert set(backup.columns("jobs")) == set(columns["jobs"])
    with backup.engine.connect() as connection:
        params = connection.execute(text("SELECT params_json FROM jobs ORDER BY id")).scalars().all()
    assert all("generation" not in str(value) for value in params)


def test_restoring_a_post_0005_backup_keeps_its_tokens(database):
    database.upgrade("0004")
    seed(database)
    database.upgrade("head")
    original = {table: database.tokens(table) for table in IDENTITY_TABLES}
    backup = database.copy("post_0005")
    assert backup.version() == "0005"
    assert {table: backup.tokens(table) for table in IDENTITY_TABLES} == original
    backup.upgrade("head")
    assert {table: backup.tokens(table) for table in IDENTITY_TABLES} == original
    assert_complete(backup)


# --- the model fields on the create_all schema --------------------------------------------------


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
