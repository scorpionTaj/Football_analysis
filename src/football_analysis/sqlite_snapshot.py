"""Atomically refresh the local read fallback from a PostgreSQL snapshot."""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
import tempfile
from datetime import date, datetime
from importlib.resources import files
from pathlib import Path

from .api.postgres_matches import _connect, _schema_name
from .config import DATA


LOCAL_SNAPSHOT = DATA / "football.sqlite3"


def _quoted(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def _sqlite_value(value):
    if isinstance(value, (date, datetime)):
        return value.isoformat(sep=" ") if isinstance(value, datetime) else value.isoformat()
    if isinstance(value, (dict, list)):
        return json.dumps(value)
    return value


def refresh_local_snapshot(dsn: str, schema: str = "football_analysis_next",
                           path: Path = LOCAL_SNAPSHOT) -> dict[str, int]:
    """Publish only a complete, count-verified SQLite copy; retain the old copy on failure."""
    from psycopg import sql

    if not dsn:
        raise ValueError("FOOTBALL_POSTGRES_DSN is required to refresh the local snapshot")
    schema = _schema_name(schema)
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    os.close(fd)
    try:
        with _connect(dsn, autocommit=True) as source, sqlite3.connect(temporary) as target:
            source.execute(sql.SQL("SET search_path TO {}").format(sql.Identifier(schema)))
            source.execute("BEGIN ISOLATION LEVEL REPEATABLE READ READ ONLY")
            tables = [row[0] for row in source.execute(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_schema = %s AND table_type = 'BASE TABLE' ORDER BY table_name", [schema],
            ).fetchall()]
            if "snapshot_manifest" not in tables:
                raise ValueError("PostgreSQL schema has no verified snapshot")
            counts = {}
            for table in tables:
                columns = source.execute(
                    "SELECT column_name FROM information_schema.columns "
                    "WHERE table_schema = %s AND table_name = %s ORDER BY ordinal_position",
                    [schema, table],
                ).fetchall()
                names = [column[0] for column in columns]
                target.execute(f"CREATE TABLE {_quoted(table)} (" + ", ".join(
                    _quoted(name) for name in names
                ) + ")")
                fields = sql.SQL(", ").join(map(sql.Identifier, names))
                with source.cursor(name=f"mirror_{table}") as reader:
                    reader.execute(sql.SQL("SELECT {} FROM {}").format(fields, sql.Identifier(table)))
                    count = 0
                    while rows := reader.fetchmany(5000):
                        target.executemany(
                            f"INSERT INTO {_quoted(table)} VALUES (" + ",".join("?" for _ in names) + ")",
                            [tuple(_sqlite_value(value) for value in row) for row in rows],
                        )
                        count += len(rows)
                expected = source.execute(sql.SQL("SELECT count(*) FROM {}").format(sql.Identifier(table))).fetchone()[0]
                if count != expected or target.execute(
                    f"SELECT count(*) FROM {_quoted(table)}"
                ).fetchone()[0] != expected:
                    raise ValueError(f"Local snapshot count mismatch for {table}")
                counts[table] = count
            for statement in files("football_analysis").joinpath("schema.sql").read_text().split(";"):
                if statement.strip().upper().startswith("CREATE OR REPLACE VIEW"):
                    target.execute(statement.replace("CREATE OR REPLACE VIEW", "CREATE VIEW", 1))
            target.execute("CREATE INDEX matches_partition ON matches (league, season)")
            target.execute("CREATE INDEX recent_partition ON recent_matches (league, season)")
            target.commit()
            source.execute("COMMIT")
        os.replace(temporary, path)
        return counts
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def main() -> None:
    parser = argparse.ArgumentParser(description="Refresh the verified local SQLite read fallback")
    parser.add_argument("--path", type=Path, default=LOCAL_SNAPSHOT)
    args = parser.parse_args()
    counts = refresh_local_snapshot(
        os.environ.get("FOOTBALL_POSTGRES_DSN", ""),
        os.environ.get("FOOTBALL_POSTGRES_SCHEMA", "football_analysis_next"), args.path,
    )
    print(json.dumps({"tables": len(counts), "rows": sum(counts.values()), "path": str(args.path)}))


if __name__ == "__main__":
    main()
