"""Alembic migration coverage: upgrade head on a fresh database."""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, select

import backend.db.seed as seed_module
from backend.db.models import User

REPO_ROOT = Path(__file__).resolve().parents[1]
EXPECTED_TABLES = ["users", "sessions", "datasets", "scenarios", "jobs"]


@pytest.fixture
def migrated_sqlite(tmp_path):
    db_path = tmp_path / "migrated.db"
    os.environ["DATABASE_URL"] = f"sqlite:///{db_path.as_posix()}"
    try:
        cfg = Config(str(REPO_ROOT / "alembic.ini"))
        cfg.set_main_option("script_location", str(REPO_ROOT / "migrations"))
        command.upgrade(cfg, "head")
        yield db_path
    finally:
        os.environ.pop("DATABASE_URL", None)


def test_upgrade_head_creates_all_tables(migrated_sqlite):
    engine = create_engine(f"sqlite:///{migrated_sqlite.as_posix()}")
    tables = set(inspect(engine).get_table_names())
    for table in EXPECTED_TABLES:
        assert table in tables, f"missing table {table}"


def test_upgrade_head_is_idempotent(migrated_sqlite):
    cfg = Config(str(REPO_ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(REPO_ROOT / "migrations"))
    command.upgrade(cfg, "head")
    command.downgrade(cfg, "base")
    command.upgrade(cfg, "head")
    engine = create_engine(f"sqlite:///{migrated_sqlite.as_posix()}")
    tables = set(inspect(engine).get_table_names())
    assert set(EXPECTED_TABLES) <= tables


def test_seed_user_creates_then_is_idempotent(tmp_path, monkeypatch):
    engine = create_engine(f"sqlite:///{(tmp_path / 'seed.db').as_posix()}")
    monkeypatch.setattr(seed_module, "get_engine", lambda: engine)
    assert seed_module.seed_user("a@example.com", "secret", "admin") == "created"
    assert seed_module.seed_user("a@example.com", "secret2", "admin") == "exists"
    with engine.connect() as conn:
        row = conn.execute(select(User).where(User.email == "a@example.com")).mappings().one()
    assert row["role"] == "admin"
    assert row["active"] is True
    assert seed_module.verify_password("secret", row["password_hash"]) is True
    assert seed_module.verify_password("secret2", row["password_hash"]) is False


def test_seed_user_force_reset_changes_password(tmp_path, monkeypatch):
    engine = create_engine(f"sqlite:///{(tmp_path / 'seed-force.db').as_posix()}")
    monkeypatch.setattr(seed_module, "get_engine", lambda: engine)
    assert seed_module.seed_user("b@example.com", "oldpass", "admin") == "created"
    assert seed_module.seed_user("b@example.com", "newpass", "admin", force=True) == "updated"
    with engine.connect() as conn:
        row = conn.execute(select(User).where(User.email == "b@example.com")).mappings().one()
    assert seed_module.verify_password("newpass", row["password_hash"]) is True
    assert seed_module.verify_password("oldpass", row["password_hash"]) is False


def test_hash_password_roundtrip():
    hashed = seed_module.hash_password("hunter2")
    assert hashed != "hunter2"
    assert seed_module.verify_password("hunter2", hashed) is True
    assert seed_module.verify_password("wrong", hashed) is False
