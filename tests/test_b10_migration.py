"""Migration 0006 (B10): datasets.purpose, added in place so the 0005 generation guards survive.

Spec: docs/superpowers/specs/2026-10-09-b10-planning-vs-review-file.md, test 10. SQLite here; the
PostgreSQL chain runs in tests/test_postgres_migration_chain.py when a PostgreSQL test database is set.
Data: SYNTHETIC rows inserted at revision 0005.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import IntegrityError

REPO_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def at_0005(tmp_path):
    db_path = tmp_path / "b10.db"
    os.environ["DATABASE_URL"] = f"sqlite:///{db_path.as_posix()}"
    cfg = Config(str(REPO_ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(REPO_ROOT / "migrations"))
    try:
        command.upgrade(cfg, "0005")
        engine = create_engine(f"sqlite:///{db_path.as_posix()}")
        with engine.begin() as connection:
            connection.execute(text(
                "INSERT INTO users (id, email, email_normalized, password_hash, role, active) "
                "VALUES (1, 'a@example.com', 'a@example.com', 'x', 'analyst', 1)"
            ))
            for dataset_id in (11, 12):
                connection.execute(text(
                    "INSERT INTO datasets (id, user_id, name, source_filename, source_format, row_count, "
                    "normalized_json, validation_report_json) "
                    f"VALUES ({dataset_id}, 1, 'd', 'd.csv', 'csv', 0, '[]', '{{\"ok\": true}}')"
                ))
        yield cfg, engine
    finally:
        os.environ.pop("DATABASE_URL", None)


def _columns(engine) -> dict:
    return {column["name"]: column for column in inspect(engine).get_columns("datasets")}


def _generations(engine) -> dict[int, str]:
    with engine.connect() as connection:
        return dict(connection.execute(text("SELECT id, generation FROM datasets")).all())


def _triggers(engine) -> list[str]:
    with engine.connect() as connection:
        return sorted(connection.execute(text(
            "SELECT name FROM sqlite_master WHERE type = 'trigger' AND tbl_name = 'datasets'"
        )).scalars().all())


def test_upgrade_marks_every_existing_dataset_as_planning_and_keeps_the_guards(at_0005):
    cfg, engine = at_0005
    generations, triggers = _generations(engine), _triggers(engine)
    assert triggers  # the 0005 guards are installed on datasets
    command.upgrade(cfg, "0006")
    column = _columns(engine)["purpose"]
    assert column["nullable"] is False
    with engine.connect() as connection:
        assert dict(connection.execute(text("SELECT id, purpose FROM datasets")).all()) == {11: "planning", 12: "planning"}
    assert _generations(engine) == generations
    assert _triggers(engine) == triggers
    with engine.begin() as connection, pytest.raises(IntegrityError):
        connection.execute(text("UPDATE datasets SET generation = 'b' || generation WHERE id = 11"))


def test_the_database_refuses_an_unknown_purpose(at_0005):
    cfg, engine = at_0005
    command.upgrade(cfg, "0006")
    with engine.begin() as connection:
        connection.execute(text("UPDATE datasets SET purpose = 'review' WHERE id = 12"))
    with engine.begin() as connection, pytest.raises(IntegrityError):
        connection.execute(text("UPDATE datasets SET purpose = 'later' WHERE id = 11"))


def test_upgrade_is_idempotent_and_downgrade_removes_only_the_column(at_0005):
    cfg, engine = at_0005
    generations, triggers = _generations(engine), _triggers(engine)
    command.upgrade(cfg, "0006")
    command.upgrade(cfg, "head")
    command.downgrade(cfg, "0005")
    assert "purpose" not in _columns(engine)
    assert _generations(engine) == generations
    assert _triggers(engine) == triggers
    command.upgrade(cfg, "head")
    assert "purpose" in _columns(engine)
