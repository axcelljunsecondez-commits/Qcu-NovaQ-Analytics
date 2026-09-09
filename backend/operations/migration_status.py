"""Fail unless the configured database is at every Alembic head."""

from __future__ import annotations

from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory

from backend.api.settings import database_url_from_environment
from backend.db.session import create_engine_for


def main() -> None:
    config = Config("alembic.ini")
    expected = set(ScriptDirectory.from_config(config).get_heads())
    engine = create_engine_for(database_url_from_environment())
    try:
        with engine.connect() as connection:
            actual = set(MigrationContext.configure(connection).get_current_heads())
    finally:
        engine.dispose()
    if actual != expected:
        raise SystemExit(
            f"Database migration mismatch: expected {sorted(expected)}, got {sorted(actual)}."
        )
    print(f"Database migration status: {','.join(sorted(actual))}")


if __name__ == "__main__":
    main()
