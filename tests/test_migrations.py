"""Alembic migration coverage: upgrade head on a fresh database."""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, select, text

import backend.db.seed as seed_module
from backend.db.models import User

REPO_ROOT = Path(__file__).resolve().parents[1]
EXPECTED_TABLES = [
    "users",
    "sessions",
    "datasets",
    "scenarios",
    "jobs",
    "analysis_projects",
    "auth_identities",
    "auth_challenges",
]


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
    user_columns = {column["name"] for column in inspect(engine).get_columns("users")}
    assert {"email_normalized", "email_verified_at"} <= user_columns


def test_upgrade_head_is_idempotent(migrated_sqlite):
    cfg = Config(str(REPO_ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(REPO_ROOT / "migrations"))
    command.upgrade(cfg, "head")
    command.downgrade(cfg, "base")
    command.upgrade(cfg, "head")
    engine = create_engine(f"sqlite:///{migrated_sqlite.as_posix()}")
    tables = set(inspect(engine).get_table_names())
    assert set(EXPECTED_TABLES) <= tables


def test_upgrade_backfills_legacy_rows_per_user(tmp_path):
    db_path = tmp_path / "legacy.db"
    os.environ["DATABASE_URL"] = f"sqlite:///{db_path.as_posix()}"
    try:
        cfg = Config(str(REPO_ROOT / "alembic.ini"))
        cfg.set_main_option("script_location", str(REPO_ROOT / "migrations"))
        command.upgrade(cfg, "0001")
        engine = create_engine(f"sqlite:///{db_path.as_posix()}")
        with engine.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO users (id,email,password_hash,role,active) VALUES "
                    "(1,'one@example.com','x','analyst',1),"
                    "(2,'two@example.com','x','analyst',1)"
                )
            )
            conn.execute(
                text(
                    "INSERT INTO datasets "
                    "(id,user_id,name,source_filename,source_format,row_count,normalized_json,validation_report_json) "
                    "VALUES (10,1,'Legacy data','legacy.csv','csv',1,'[]','{}')"
                )
            )
            conn.execute(
                text(
                    "INSERT INTO scenarios "
                    "(id,user_id,dataset_id,name,settings_json,results_json) VALUES "
                    "(20,1,10,'Linked','{}','{}'),"
                    "(21,1,NULL,'Loose one','{}','{}'),"
                    "(22,2,NULL,'Loose two','{}','{}'),"
                    "(23,2,10,'Inconsistent','{}','{}')"
                )
            )
        with pytest.warns(UserWarning, match="cannot be assigned safely|could not be assigned safely"):
            command.upgrade(cfg, "head")
        with engine.connect() as conn:
            dataset_analysis = conn.execute(
                text("SELECT analysis_id FROM datasets WHERE id=10")
            ).scalar_one()
            linked_analysis = conn.execute(
                text("SELECT analysis_id FROM scenarios WHERE id=20")
            ).scalar_one()
            loose = conn.execute(
                text("SELECT id,user_id,analysis_id FROM scenarios WHERE id IN (21,22) ORDER BY id")
            ).mappings().all()
            inconsistent = conn.execute(
                text("SELECT analysis_id FROM scenarios WHERE id=23")
            ).scalar_one_or_none()
            names = conn.execute(
                text("SELECT user_id,name FROM analysis_projects ORDER BY id")
            ).all()
        assert dataset_analysis == linked_analysis
        assert loose[0]["analysis_id"] != loose[1]["analysis_id"]
        assert inconsistent is None
        assert (1, "Legacy data") in names
        assert names.count((1, "Legacy scenarios")) == 1
        assert names.count((2, "Legacy scenarios")) == 1
    finally:
        os.environ.pop("DATABASE_URL", None)


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


def test_auth_migration_backfills_existing_users_as_verified(tmp_path):
    db_path = tmp_path / "auth-legacy.db"
    os.environ["DATABASE_URL"] = f"sqlite:///{db_path.as_posix()}"
    try:
        cfg = Config(str(REPO_ROOT / "alembic.ini"))
        cfg.set_main_option("script_location", str(REPO_ROOT / "migrations"))
        command.upgrade(cfg, "0002")
        engine = create_engine(f"sqlite:///{db_path.as_posix()}")
        with engine.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO users (email,password_hash,role,active) "
                    "VALUES (' Legacy@Example.COM ','unchanged','analyst',1)"
                )
            )
        command.upgrade(cfg, "head")
        with engine.connect() as conn:
            row = conn.execute(
                text("SELECT email_normalized,email_verified_at,password_hash FROM users")
            ).mappings().one()
        assert row["email_normalized"] == "legacy@example.com"
        assert row["email_verified_at"] is not None
        assert row["password_hash"] == "unchanged"
    finally:
        os.environ.pop("DATABASE_URL", None)


def test_auth_migration_rejects_normalized_email_collisions(tmp_path):
    db_path = tmp_path / "auth-collision.db"
    os.environ["DATABASE_URL"] = f"sqlite:///{db_path.as_posix()}"
    try:
        cfg = Config(str(REPO_ROOT / "alembic.ini"))
        cfg.set_main_option("script_location", str(REPO_ROOT / "migrations"))
        command.upgrade(cfg, "0002")
        engine = create_engine(f"sqlite:///{db_path.as_posix()}")
        with engine.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO users (id,email,password_hash,role,active) VALUES "
                    "(101,'Case@Example.com','x','analyst',1),"
                    "(102,' case@example.COM ','y','analyst',1)"
                )
            )
        with pytest.raises(RuntimeError, match=r"case@example.com.*101.*102"):
            command.upgrade(cfg, "head")
    finally:
        os.environ.pop("DATABASE_URL", None)
