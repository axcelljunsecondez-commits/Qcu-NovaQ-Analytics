"""G7: a production app serves only a database exactly at the code's Alembic heads (gate G-T16).

Spec: docs/superpowers/specs/2026-09-26-generation-identity-contract.md §1 rule 6, §11.1, §11.3, §13
(G-T16), §14 (G7) and §15.3. Decisions of 2026-09-29:

- D1: exact head equality; no subset, no superset.
- D2: only ``Settings.environment == "production"``. Development, test and integration are unchanged.
  The rehearsal stack's ``api`` service runs as production and is therefore guarded; its
  ``api-restored`` service runs as integration and is not.
- D3: fail closed. Heads that cannot be determined, a revision that cannot be read, and any other
  revision refuse startup.
- D4: ``/ready`` keeps "Database not ready." for connectivity and answers a schema that is not, or cannot
  be shown to be, at the heads with the approved text, naming no revision.
- D5: one implementation, shared with ``backend/operations/migration_status.py``; its CLI is unchanged.
- D6: ``entrypoint.sh`` is not changed.

The lifespan runs only when TestClient is used as a context manager, so every startup case enters
``with TestClient(app)``. A plain TestClient never starts the guard.

Databases carry real Alembic state: a disposable SQLite file, and on PostgreSQL a disposable schema in
the dedicated *_test database named by NOVAQ_TEST_DATABASE_URL (never the maintenance database). A
state no migration writes (an unknown, newer or extra revision, or no revision table) is a direct row
edit, marked SYNTHETIC.
"""

from __future__ import annotations

import contextlib
import os
import subprocess
import sys
import uuid
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
import yaml
from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import OperationalError, ProgrammingError

import backend.api.main as main_api
import backend.api.workflow as workflow_api
from backend.api.email_delivery import FakeEmailSender
from backend.api.main import create_app
from backend.api.settings import Settings
from backend.db.base import Base
from backend.operations import migration_status
from tests.test_production_hardening import production_environment

REPO_ROOT = Path(__file__).resolve().parents[1]
NOT_READY = "Database not ready."
# D4: the approved readiness text, written out so that a change to the application's text is caught.
SCHEMA_NOT_AT_REVISION = "Database schema is not at the required migration revision."
DIALECTS = ["sqlite", "postgresql"]


def _alembic_config() -> Config:
    config = Config(str(REPO_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(REPO_ROOT / "migrations"))
    return config


# Read from the scripts here, independently of the code under test.
_SCRIPT = ScriptDirectory.from_config(_alembic_config())
CODE_HEADS = sorted(_SCRIPT.get_heads())
PREVIOUS = str(_SCRIPT.get_revision(CODE_HEADS[0]).down_revision)


def _mismatch(actual: list[str]) -> str:
    return f"Database migration mismatch: expected {CODE_HEADS}, got {sorted(actual)}."


class RevisionDatabase:
    """A disposable database whose Alembic state is set through the repository's migration chain."""

    def __init__(self, url: str, dialect: str, monkeypatch: Any) -> None:
        self.url = url
        self.dialect = dialect
        self._monkeypatch = monkeypatch
        connect_args = {"check_same_thread": False} if dialect == "sqlite" else {}
        self.engine = create_engine(url, connect_args=connect_args)

    def upgrade(self, revision: str = "head") -> None:
        self._monkeypatch.setenv("DATABASE_URL", self.url)
        command.upgrade(_alembic_config(), revision)

    def build_without_migrations(self) -> None:
        """The schema ``create_all`` builds (tests, a seed on an empty database): no revision table."""
        Base.metadata.create_all(self.engine)

    def set_revisions(self, *revisions: str) -> None:
        """SYNTHETIC (direct row edit): the rows of ``alembic_version``."""
        with self.engine.begin() as connection:
            connection.execute(text("DELETE FROM alembic_version"))
            for revision in revisions:
                connection.execute(text("INSERT INTO alembic_version (version_num) VALUES (:r)"), {"r": revision})

    def drop_revision_table(self) -> None:
        """SYNTHETIC (direct row edit): no ``alembic_version`` table at all."""
        with self.engine.begin() as connection:
            connection.execute(text("DROP TABLE alembic_version"))


@contextlib.contextmanager
def open_revision_database(dialect: str, directory: Path, monkeypatch: Any) -> Iterator[RevisionDatabase]:
    if dialect == "sqlite":
        database = RevisionDatabase(f"sqlite:///{(directory / 'g7.db').as_posix()}", "sqlite", monkeypatch)
        try:
            yield database
        finally:
            database.engine.dispose()
        return
    source = os.environ.get("NOVAQ_TEST_DATABASE_URL")
    if not source:
        pytest.skip("NOVAQ_TEST_DATABASE_URL is required for the PostgreSQL variant")
    url = make_url(source)
    if url.get_backend_name() != "postgresql" or not (url.database or "").endswith("_test"):
        pytest.fail("The PostgreSQL variant requires a dedicated database ending in _test")
    schema = "novaq_g7_" + uuid.uuid4().hex
    owner = create_engine(url)
    with owner.begin() as connection:
        connection.execute(text(f'CREATE SCHEMA "{schema}"'))
    scoped = url.update_query_dict({"options": f"-csearch_path={schema}"})
    database = RevisionDatabase(scoped.render_as_string(hide_password=False), "postgresql", monkeypatch)
    try:
        yield database
    finally:
        database.engine.dispose()
        with owner.begin() as connection:
            connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        owner.dispose()


@pytest.fixture(params=DIALECTS)
def revision_db(request, tmp_path, monkeypatch) -> Iterator[RevisionDatabase]:
    with open_revision_database(request.param, tmp_path, monkeypatch) as database:
        yield database


@pytest.fixture
def sqlite_revision_db(tmp_path, monkeypatch) -> Iterator[RevisionDatabase]:
    with open_revision_database("sqlite", tmp_path, monkeypatch) as database:
        yield database


def _app(database: RevisionDatabase, environment: str, monkeypatch: Any):
    """The application on ``database`` with settings for ``environment``; the database is injected."""
    if environment == "production":
        production_environment(monkeypatch)
    else:
        monkeypatch.setenv("NOVAQ_ENV", environment)
    return create_app(engine=database.engine, settings=Settings(), email_sender=FakeEmailSender())


def _refusal(app) -> str:
    """Start ``app`` (its lifespan runs) and return why it refused. Fails if it started."""
    with pytest.raises(RuntimeError) as refused:
        with TestClient(app):
            pass
    return str(refused.value)


def _ready(client: TestClient) -> tuple[int, Any]:
    response = client.get("/ready")
    return response.status_code, response.json()


# -- Production startup (G-T16) ------------------------------------------------------------------------


def test_production_starts_and_is_ready_at_the_exact_head(revision_db, monkeypatch):
    revision_db.upgrade("head")
    app = _app(revision_db, "production", monkeypatch)
    with TestClient(app) as client:
        assert _ready(client) == (200, {"status": "ready"})
        assert sorted(app.state.required_heads) == CODE_HEADS


def test_production_refuses_the_previous_revision(revision_db, monkeypatch):
    revision_db.upgrade(PREVIOUS)
    assert _refusal(_app(revision_db, "production", monkeypatch)) == _mismatch([PREVIOUS])


@pytest.mark.parametrize("build", ["create-all-only", "no-rows", "no-table"])
def test_production_refuses_a_database_with_no_recorded_revision(revision_db, monkeypatch, build):
    if build == "create-all-only":
        revision_db.build_without_migrations()
    else:
        revision_db.upgrade("head")
        if build == "no-rows":
            revision_db.set_revisions()
        else:
            revision_db.drop_revision_table()
    assert _refusal(_app(revision_db, "production", monkeypatch)) == _mismatch([])


@pytest.mark.parametrize("recorded", [["0006"], ["ffffffffffff"]], ids=["newer", "unknown"])
def test_production_refuses_an_unknown_or_newer_revision(revision_db, monkeypatch, recorded):
    revision_db.upgrade("head")
    revision_db.set_revisions(*recorded)
    assert _refusal(_app(revision_db, "production", monkeypatch)) == _mismatch(recorded)


@pytest.mark.parametrize("extra", [PREVIOUS, "0006"], ids=["with-previous", "with-newer"])
def test_production_refuses_extra_recorded_heads(revision_db, monkeypatch, extra):
    """A superset of the code's heads is not the code's heads (D1)."""
    revision_db.upgrade("head")
    revision_db.set_revisions(*CODE_HEADS, extra)
    assert _refusal(_app(revision_db, "production", monkeypatch)) == _mismatch([*CODE_HEADS, extra])


def test_production_refuses_an_unreachable_database(revision_db, monkeypatch):
    revision_db.upgrade("head")
    app = _app(revision_db, "production", monkeypatch)

    def unavailable(*args, **kwargs):
        raise OperationalError("connect", {}, Exception("unavailable"))

    monkeypatch.setattr(revision_db.engine, "connect", unavailable)
    assert _refusal(app) == "Database migration revision cannot be read (OperationalError)."


def test_production_refuses_an_unreadable_revision_table(revision_db, monkeypatch):
    revision_db.upgrade("head")
    app = _app(revision_db, "production", monkeypatch)

    class Unreadable:
        @staticmethod
        def configure(connection):
            raise ProgrammingError("SELECT version_num FROM alembic_version", {}, Exception("permission denied"))

    monkeypatch.setattr(migration_status, "MigrationContext", Unreadable)
    assert _refusal(app) == "Database migration revision cannot be read (ProgrammingError)."


def _layout(root: Path, *, ini: bool, scripts: str) -> Path:
    """A package root for the guard: ``scripts`` is "full" (a copy of every migration), "empty" (a
    versions directory with no migration) or "missing"."""
    root.mkdir()
    if ini:
        (root / "alembic.ini").write_bytes((REPO_ROOT / "alembic.ini").read_bytes())
    if scripts != "missing":
        versions = root / "migrations" / "versions"
        versions.mkdir(parents=True)
        (root / "migrations" / "script.py.mako").write_bytes((REPO_ROOT / "migrations" / "script.py.mako").read_bytes())
        if scripts == "full":
            for source in (REPO_ROOT / "migrations" / "versions").glob("*.py"):
                (versions / source.name).write_bytes(source.read_bytes())
    return root


@pytest.mark.parametrize(("ini", "scripts", "cause"), [
    pytest.param(False, "full", "FileNotFoundError", id="no-alembic-ini"),
    pytest.param(True, "missing", "FileNotFoundError", id="no-migrations-directory"),
    pytest.param(True, "empty", "LookupError", id="no-head"),
])
def test_production_refuses_when_the_code_heads_cannot_be_determined(sqlite_revision_db, monkeypatch, tmp_path,
                                                                      ini, scripts, cause):
    sqlite_revision_db.upgrade("head")
    monkeypatch.setattr(main_api, "REPO_ROOT", _layout(tmp_path / "package", ini=ini, scripts=scripts))
    refusal = _refusal(_app(sqlite_revision_db, "production", monkeypatch))
    assert refusal.startswith(f"Database migration heads cannot be determined ({cause}: ")


def test_the_layout_helper_reproduces_a_working_package(sqlite_revision_db, monkeypatch, tmp_path):
    """Control for the case above: the same copy with nothing removed starts."""
    sqlite_revision_db.upgrade("head")
    monkeypatch.setattr(main_api, "REPO_ROOT", _layout(tmp_path / "package", ini=True, scripts="full"))
    with TestClient(_app(sqlite_revision_db, "production", monkeypatch)) as client:
        assert _ready(client) == (200, {"status": "ready"})


def test_the_guard_does_not_depend_on_the_working_directory(sqlite_revision_db, monkeypatch, tmp_path):
    sqlite_revision_db.upgrade("head")
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    monkeypatch.chdir(elsewhere)
    with TestClient(_app(sqlite_revision_db, "production", monkeypatch)) as client:
        assert _ready(client) == (200, {"status": "ready"})


# -- Production readiness ---------------------------------------------------------------------------------


def test_ready_reads_the_revision_again_on_every_call(revision_db, monkeypatch):
    revision_db.upgrade("head")
    with TestClient(_app(revision_db, "production", monkeypatch)) as client:
        assert _ready(client) == (200, {"status": "ready"})
        for recorded in ([PREVIOUS], [], ["0006"], [*CODE_HEADS, "0006"]):
            revision_db.set_revisions(*recorded)                  # SYNTHETIC: changed under the process
            status, body = _ready(client)
            assert (status, body) == (503, {"detail": SCHEMA_NOT_AT_REVISION}), recorded
            assert not any(revision in str(body) for revision in [*CODE_HEADS, PREVIOUS, "0006"])
            revision_db.set_revisions(*CODE_HEADS)
            assert _ready(client) == (200, {"status": "ready"})
        revision_db.drop_revision_table()
        assert _ready(client) == (503, {"detail": SCHEMA_NOT_AT_REVISION})


def test_ready_keeps_the_connectivity_text(revision_db, monkeypatch):
    revision_db.upgrade("head")
    with TestClient(_app(revision_db, "production", monkeypatch)) as client:
        def unavailable(*args, **kwargs):
            raise OperationalError("connect", {}, Exception("unavailable"))

        monkeypatch.setattr(revision_db.engine, "connect", unavailable)
        assert _ready(client) == (503, {"detail": NOT_READY})


def test_ready_answers_an_unreadable_revision_with_the_schema_text(revision_db, monkeypatch):
    revision_db.upgrade("head")
    with TestClient(_app(revision_db, "production", monkeypatch)) as client:
        class Unreadable:
            @staticmethod
            def configure(connection):
                raise ProgrammingError("SELECT version_num FROM alembic_version", {}, Exception("denied"))

        monkeypatch.setattr(migration_status, "MigrationContext", Unreadable)
        assert _ready(client) == (503, {"detail": SCHEMA_NOT_AT_REVISION})


def test_ready_is_not_ready_when_startup_never_verified_the_heads(revision_db, monkeypatch):
    """A production app whose lifespan did not run has no verified heads: unverified, never a match."""
    revision_db.upgrade("head")
    client = TestClient(_app(revision_db, "production", monkeypatch))    # no lifespan
    assert _ready(client) == (503, {"detail": SCHEMA_NOT_AT_REVISION})


# -- Every other environment is unchanged (D2) -------------------------------------------------------------


@pytest.mark.parametrize("environment", ["development", "test", "integration"])
@pytest.mark.parametrize("build", ["previous", "create-all-only"])
def test_non_production_environments_run_no_guard(revision_db, monkeypatch, environment, build):
    if build == "previous":
        revision_db.upgrade(PREVIOUS)
    else:
        revision_db.build_without_migrations()
    app = _app(revision_db, environment, monkeypatch)
    with TestClient(app) as client:
        assert _ready(client) == (200, {"status": "ready"})
    assert not hasattr(app.state, "required_heads")


def test_the_stacks_run_the_environments_the_guard_keys_on():
    """D2 as deployed by the repository's stacks: the integration API and the restored rehearsal API run
    as integration (unguarded); the rehearsal API runs as production (guarded), and both integration
    stacks start their API only after ``migrate`` has upgraded and checked the revision."""
    integration = yaml.safe_load((REPO_ROOT / "docker-compose.integration.yml").read_text(encoding="utf-8"))
    rehearsal = yaml.safe_load((REPO_ROOT / "docker-compose.rehearsal.yml").read_text(encoding="utf-8"))
    services = integration["services"]
    assert services["api"]["environment"]["NOVAQ_ENV"] == "integration"
    assert rehearsal["services"]["api-restored"]["environment"]["NOVAQ_ENV"] == "integration"
    assert rehearsal["services"]["api"]["environment"]["NOVAQ_ENV"] == "production"
    assert services["migrate"]["command"][-1] == "alembic upgrade head && python -m backend.operations.migration_status"
    assert services["bootstrap-admin"]["depends_on"]["migrate"]["condition"] == "service_completed_successfully"
    assert services["api"]["depends_on"]["bootstrap-admin"]["condition"] == "service_completed_successfully"


# -- Independent of generation enforcement -----------------------------------------------------------------


@pytest.mark.parametrize("enforced", [False, True], ids=["enforcement-off", "enforcement-on"])
def test_the_guard_is_independent_of_generation_enforcement(revision_db, monkeypatch, enforced):
    monkeypatch.setattr(workflow_api, "GENERATION_ENFORCEMENT_ENABLED", enforced)
    revision_db.upgrade(PREVIOUS)
    assert _refusal(_app(revision_db, "production", monkeypatch)) == _mismatch([PREVIOUS])
    revision_db.upgrade("head")
    with TestClient(_app(revision_db, "production", monkeypatch)) as client:
        assert _ready(client) == (200, {"status": "ready"})


# -- The migration_status CLI is unchanged (D5) -----------------------------------------------------------


def test_migration_status_cli_behaviour_is_unchanged(revision_db, monkeypatch, capsys, tmp_path):
    revision_db.upgrade(PREVIOUS)
    monkeypatch.chdir(REPO_ROOT)
    monkeypatch.setenv("DATABASE_URL", revision_db.url)
    with pytest.raises(SystemExit) as refused:
        migration_status.main()
    assert refused.value.code == _mismatch([PREVIOUS])
    revision_db.upgrade("head")
    monkeypatch.setenv("DATABASE_URL", revision_db.url)
    migration_status.main()
    assert capsys.readouterr().out == f"Database migration status: {','.join(CODE_HEADS)}\n"
    # The CLI still reads alembic.ini from the working directory, as before G7.
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    monkeypatch.chdir(elsewhere)
    with pytest.raises(Exception, match="script_location"):
        migration_status.main()


# -- A real server start -----------------------------------------------------------------------------------

SERVED_APP = """
from sqlalchemy import create_engine

from backend.api.email_delivery import FakeEmailSender
from backend.api.main import create_app
from backend.api.settings import Settings

app = create_app(engine=create_engine({url!r}, connect_args={{"check_same_thread": False}}),
                 settings=Settings(), email_sender=FakeEmailSender())
"""


def test_uvicorn_refuses_to_serve_a_production_app_on_the_previous_revision(sqlite_revision_db, monkeypatch,
                                                                             tmp_path):
    """Spec §15.3 on this app: the lifespan refusal stops uvicorn with exit code 3 before serving. Run
    with the locally installed uvicorn, not the production pins."""
    sqlite_revision_db.upgrade(PREVIOUS)
    production_environment(monkeypatch)
    module = tmp_path / "served"
    module.mkdir()
    (module / "g7_served_app.py").write_text(SERVED_APP.format(url=sqlite_revision_db.url), encoding="utf-8")
    environment = {**os.environ, "PYTHONPATH": os.pathsep.join([str(module), str(REPO_ROOT)])}
    result = subprocess.run(
        [sys.executable, "-m", "uvicorn", "g7_served_app:app", "--host", "127.0.0.1", "--port", "0"],
        cwd=module, env=environment, capture_output=True, text=True, timeout=120,
    )
    assert result.returncode == 3, result.stderr[-2000:]
    assert "Application startup failed. Exiting." in result.stderr
    assert _mismatch([PREVIOUS]) in result.stderr
