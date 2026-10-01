"""Fail unless the configured database is at every Alembic head."""

from __future__ import annotations

from pathlib import Path

from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy.engine import Connection, Engine

from backend.api.settings import database_url_from_environment
from backend.db.session import create_engine_for


def expected_heads(config: Config) -> set[str]:
    """Every head of the script directory ``config`` names: the revisions the code requires."""
    return set(ScriptDirectory.from_config(config).get_heads())


def current_heads(connection: Connection) -> set[str]:
    """Every revision the database records in ``alembic_version``, exactly as stored."""
    return set(MigrationContext.configure(connection).get_current_heads())


def head_mismatch(expected: set[str], actual: set[str]) -> str | None:
    """The mismatch message unless the database is exactly at the code's heads: no subset, no superset."""
    if actual != expected:
        return f"Database migration mismatch: expected {sorted(expected)}, got {sorted(actual)}."
    return None


def code_config(ini_path: Path, script_location: Path) -> Config:
    """An Alembic configuration for explicit paths, independent of the working directory.

    Raises when either path is missing. Alembic itself reads a missing ini file as an empty one, so a
    caller that must fail closed would otherwise check against a partial configuration.
    """
    if not ini_path.is_file():
        raise FileNotFoundError(f"Alembic configuration not found: {ini_path}")
    if not script_location.is_dir():
        raise FileNotFoundError(f"Alembic script directory not found: {script_location}")
    config = Config(str(ini_path))
    config.set_main_option("script_location", str(script_location).replace("%", "%%"))
    return config


def required_heads(config: Config) -> set[str]:
    """The code's heads for a check that must fail closed (spec 2026-09-26 G7, decision D3).

    Raises when they cannot be determined. A script directory with no head is undetermined, never a
    statement that the database needs no revision.
    """
    heads = expected_heads(config)
    if not heads:
        raise LookupError("The Alembic script directory has no head.")
    return heads


def schema_head_problem(engine: Engine, expected: set[str]) -> str | None:
    """Why the database behind ``engine`` is not exactly at ``expected``, or None when it is.

    A revision that cannot be read (the database is unreachable, or ``alembic_version`` is unreadable)
    is a problem, never a match (G7, decision D3).
    """
    try:
        with engine.connect() as connection:
            actual = current_heads(connection)
    except Exception as exc:
        return f"Database migration revision cannot be read ({type(exc).__name__})."
    return head_mismatch(expected, actual)


def main() -> None:
    expected = expected_heads(Config("alembic.ini"))
    engine = create_engine_for(database_url_from_environment())
    try:
        with engine.connect() as connection:
            actual = current_heads(connection)
    finally:
        engine.dispose()
    mismatch = head_mismatch(expected, actual)
    if mismatch is not None:
        raise SystemExit(mismatch)
    print(f"Database migration status: {','.join(sorted(actual))}")


if __name__ == "__main__":
    main()
