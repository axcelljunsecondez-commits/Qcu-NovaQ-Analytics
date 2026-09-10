"""Test-session bootstrap + shared fixtures.

Bootstrap makes the repository root importable (for ``backend.*`` packages)
regardless of how pytest is invoked.
"""

from __future__ import annotations

import os
import sys
import uuid
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

from backend.api.email_delivery import FakeEmailSender
from backend.api.main import create_app
from backend.api.settings import Settings
from backend.db.base import Base
from tests.helpers import make_sessionmaker

_ROOT = Path(__file__).resolve().parent.parent

for _path in (str(_ROOT),):
    if _path not in sys.path:
        sys.path.insert(0, _path)

os.environ.setdefault("LOG_LEVEL", "WARNING")


@pytest.fixture
def db_engine(tmp_path):
    test_url = os.environ.get("NOVAQ_TEST_DATABASE_URL")
    if test_url:
        url = make_url(test_url)
        if url.get_backend_name() != "postgresql" or not (url.database or "").endswith("_test"):
            raise RuntimeError("Integration tests require a dedicated Postgres database ending in _test")
        schema = "novaq_test_" + uuid.uuid4().hex
        admin = create_engine(url)
        with admin.begin() as connection:
            connection.execute(text(f'CREATE SCHEMA "{schema}"'))
        engine = create_engine(url, connect_args={"options": f"-csearch_path={schema}"})
        try:
            Base.metadata.create_all(engine)
            yield engine
        finally:
            engine.dispose()
            with admin.begin() as connection:
                connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
            admin.dispose()
        return
    engine = create_engine(
        f"sqlite:///{(tmp_path / 'test.db').as_posix()}", connect_args={"check_same_thread": False}
    )
    Base.metadata.create_all(engine)
    yield engine
    engine.dispose()


@pytest.fixture
def app(db_engine):
    return create_app(engine=db_engine, settings=Settings(), email_sender=FakeEmailSender())


@pytest.fixture
def client(app):
    return TestClient(app)


@pytest.fixture
def session_factory(db_engine):
    """Session factory bound to the test database (for direct row access)."""
    return make_sessionmaker(db_engine)


@pytest.fixture
def email_sender(app):
    return app.state.email_sender
