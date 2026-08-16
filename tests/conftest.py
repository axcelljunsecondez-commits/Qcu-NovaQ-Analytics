"""Test-session bootstrap + shared fixtures.

Bootstrap makes the repository root importable (for ``backend.*`` packages)
regardless of how pytest is invoked.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine

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
    engine = create_engine(
        f"sqlite:///{(tmp_path / 'test.db').as_posix()}", connect_args={"check_same_thread": False}
    )
    Base.metadata.create_all(engine)
    yield engine
    engine.dispose()


@pytest.fixture
def app(db_engine):
    return create_app(engine=db_engine, settings=Settings())


@pytest.fixture
def client(app):
    return TestClient(app)


@pytest.fixture
def session_factory(db_engine):
    """Session factory bound to the test database (for direct row access)."""
    return make_sessionmaker(db_engine)
