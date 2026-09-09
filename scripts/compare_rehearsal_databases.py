"""Compare only fixed synthetic rehearsal databases on the disposable Docker network."""
from __future__ import annotations

import hashlib
import json

import psycopg
from psycopg import sql


def snapshot(database: str) -> dict:
    assert database in {"novaq_test", "novaq_restore_test"}
    output = {}
    with psycopg.connect(host="db", user="novaq_test", password="integration-only", dbname=database) as connection:
        tables = connection.execute("SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY tablename").fetchall()
        for (table,) in tables:
            statement = sql.SQL("SELECT to_jsonb(t) FROM public.{} t ORDER BY to_jsonb(t)::text").format(sql.Identifier(table))
            rows = [row[0] for row in connection.execute(statement).fetchall()]
            payload = json.dumps(rows, sort_keys=True, separators=(",", ":")).encode()
            output[table] = {"rows": len(rows), "sha256": hashlib.sha256(payload).hexdigest()}
    return output


def main() -> None:
    source = snapshot("novaq_test")
    restored = snapshot("novaq_restore_test")
    assert source == restored, "Restored table contents differ from source"
    assert all(source[table]["rows"] >= 1 for table in ("users", "datasets", "scenarios")), "Empty fixtures cannot verify recovery"
    print(json.dumps(source, indent=2))
    print("PASS: every public table matches after backup/restore")


if __name__ == "__main__":
    main()
