"""Migration 0007 (B4a): analysis_projects.shared_closing_policy, added in place and null for every analysis.

Spec: docs/superpowers/specs/2026-10-09-b4a-continuous-shared-run-preview.md (OD-B4a-1 = A). SQLite here;
the PostgreSQL chain runs in tests/test_postgres_migration_chain.py when a PostgreSQL test database is set.
Data: SYNTHETIC rows inserted at revision 0006.
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
SETUP = '{"queue_structure": "shared_queue"}'


@pytest.fixture
def at_0006(tmp_path):
    db_path = tmp_path / "b4a.db"
    os.environ["DATABASE_URL"] = f"sqlite:///{db_path.as_posix()}"
    cfg = Config(str(REPO_ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(REPO_ROOT / "migrations"))
    try:
        command.upgrade(cfg, "0006")
        engine = create_engine(f"sqlite:///{db_path.as_posix()}")
        with engine.begin() as connection:
            connection.execute(text(
                "INSERT INTO users (id, email, email_normalized, password_hash, role, active) "
                "VALUES (1, 'a@example.com', 'a@example.com', 'x', 'analyst', 1)"
            ))
            for analysis_id in (21, 22):
                connection.execute(text(
                    "INSERT INTO analysis_projects (id, user_id, name, queue_setup_json, setup_status) "
                    f"VALUES ({analysis_id}, 1, 'a', '{SETUP}', 'ready')"
                ))
        yield cfg, engine
    finally:
        os.environ.pop("DATABASE_URL", None)


def _columns(engine) -> dict:
    return {column["name"]: column for column in inspect(engine).get_columns("analysis_projects")}


def _rows(engine) -> list[tuple]:
    with engine.connect() as connection:
        return connection.execute(text("SELECT id, name, queue_setup_json FROM analysis_projects ORDER BY id")).all()


def test_upgrade_leaves_every_analysis_without_a_chosen_rule(at_0006):
    cfg, engine = at_0006
    before = _rows(engine)
    command.upgrade(cfg, "0007")
    assert _columns(engine)["shared_closing_policy"]["nullable"] is True
    with engine.connect() as connection:
        assert dict(connection.execute(text("SELECT id, shared_closing_policy FROM analysis_projects")).all()) == {
            21: None, 22: None}
    assert _rows(engine) == before


def test_the_database_refuses_an_unknown_rule(at_0006):
    cfg, engine = at_0006
    command.upgrade(cfg, "0007")
    with engine.begin() as connection:
        connection.execute(text("UPDATE analysis_projects SET shared_closing_policy = 'DRAIN' WHERE id = 21"))
        connection.execute(text("UPDATE analysis_projects SET shared_closing_policy = 'HARD_CUTOFF' WHERE id = 22"))
        connection.execute(text("UPDATE analysis_projects SET shared_closing_policy = NULL WHERE id = 22"))
    with engine.begin() as connection, pytest.raises(IntegrityError):
        connection.execute(text("UPDATE analysis_projects SET shared_closing_policy = 'drain' WHERE id = 21"))


def test_upgrade_is_idempotent_and_downgrade_removes_only_the_column(at_0006):
    cfg, engine = at_0006
    before = _rows(engine)
    command.upgrade(cfg, "0007")
    command.upgrade(cfg, "head")
    command.downgrade(cfg, "0006")
    assert "shared_closing_policy" not in _columns(engine)
    assert _rows(engine) == before
    command.upgrade(cfg, "head")
    assert "shared_closing_policy" in _columns(engine)
