"""Real PostgreSQL migration-chain rehearsals; skipped without the CI test DB."""

from __future__ import annotations

import os
import uuid

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url


@pytest.mark.parametrize("starting_revision", [None, "0001", "0002"])
def test_real_postgres_upgrade_paths_preserve_ownership(starting_revision, monkeypatch):
    source = os.environ.get("NOVAQ_TEST_DATABASE_URL")
    if not source:
        pytest.skip("NOVAQ_TEST_DATABASE_URL is required for PostgreSQL migration rehearsal")
    source_url = make_url(source)
    if source_url.get_backend_name() != "postgresql" or not (source_url.database or "").endswith("_test"):
        pytest.fail("Migration rehearsal requires a dedicated PostgreSQL database ending in _test")

    database = f"novaq_migration_{uuid.uuid4().hex}_test"
    admin_url = source_url.set(database="postgres")
    target_url = source_url.set(database=database)
    admin = create_engine(admin_url, isolation_level="AUTOCOMMIT")
    with admin.connect() as connection:
        connection.execute(text(f'CREATE DATABASE "{database}"'))
    try:
        monkeypatch.setenv("DATABASE_URL", target_url.render_as_string(hide_password=False))
        config = Config("alembic.ini")
        if starting_revision:
            command.upgrade(config, starting_revision)
            target = create_engine(target_url)
            with target.begin() as connection:
                connection.execute(
                    text(
                        "INSERT INTO users (id,email,password_hash,role,active) "
                        "VALUES (101,'owner@example.com','hash','analyst',true)"
                    )
                )
                if starting_revision == "0001":
                    connection.execute(
                        text(
                            "INSERT INTO datasets "
                            "(id,user_id,name,source_filename,source_format,row_count,normalized_json,validation_report_json) "
                            "VALUES (201,101,'owned','owned.csv','csv',1,CAST('[]' AS jsonb),CAST('{}' AS jsonb))"
                        )
                    )
                    connection.execute(
                        text(
                            "INSERT INTO scenarios "
                            "(id,user_id,dataset_id,name,settings_json,results_json) "
                            "VALUES (301,101,201,'owned',CAST('{}' AS jsonb),CAST('{}' AS jsonb))"
                        )
                    )
            target.dispose()
        command.upgrade(config, "head")
        target = create_engine(target_url)
        with target.connect() as connection:
            assert connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one() == "0003"
            if starting_revision == "0001":
                row = connection.execute(
                    text(
                        "SELECT d.user_id,s.user_id,d.analysis_id,s.analysis_id "
                        "FROM datasets d JOIN scenarios s ON s.dataset_id=d.id "
                        "WHERE d.id=201"
                    )
                ).one()
                assert row[0] == row[1] == 101
                assert row[2] == row[3]
                assert row[2] is not None
            if starting_revision:
                verified = connection.execute(
                    text("SELECT email_normalized,email_verified_at FROM users WHERE id=101")
                ).one()
                assert verified[0] == "owner@example.com"
                assert verified[1] is not None
        target.dispose()
    finally:
        with admin.connect() as connection:
            connection.execute(
                text("SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname=:database"),
                {"database": database},
            )
            connection.execute(text(f'DROP DATABASE IF EXISTS "{database}"'))
        admin.dispose()
