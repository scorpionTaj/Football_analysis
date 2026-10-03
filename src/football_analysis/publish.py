"""Publish the DuckDB warehouse to its serving stores.

PostgreSQL (Supabase): incremental, verified, atomic. Each table's row digest is compared
with the schema's `snapshot_manifest`; only changed tables are copied into `<table>__next`
and all of them are swapped in one transaction, so readers never see a half-published
state and peak extra space is the size of the changed tables, not a second schema copy.

SQLite fallback: rebuilt locally from the same DuckDB tables (no network round-trip) and
atomically renamed into place; the API serves it whenever PostgreSQL is unreachable.

    uv run football-publish            # PostgreSQL (if FOOTBALL_POSTGRES_DSN) + SQLite
"""

from __future__ import annotations

import argparse
import json
import os
import re
import tempfile
from importlib.resources import files
from pathlib import Path

import duckdb
from psycopg import sql

from .config import DB, LOCAL_SNAPSHOT
from .pg import TYPES, chunks as _chunks, connect as _connect, rows_digest as _rows_digest, schema_name as _name

# Warehouse outputs served next to the app tables (published name -> DuckDB relation).
# Only what the API reads: the Supabase free tier caps the database at 500 MB, so large
# analytical tables (fct_match, backtest predictions, features) stay in DuckDB.
WAREHOUSE_TABLES = {
    "mart_team_season": "marts.mart_team_season",
    "model_runs": "ml.model_runs",
}
VIEWS = [s.strip().replace("DOUBLE", "DOUBLE PRECISION") for s in files("football_analysis").joinpath("schema.sql").read_text().split(";")
         if s.strip().upper().startswith("CREATE OR REPLACE VIEW")]


def served_tables(con) -> dict[str, str]:
    """Published name -> DuckDB relation for every table the API may read."""
    app = {row[0]: f'main."{row[0]}"' for row in con.execute(
        "SELECT table_name FROM information_schema.tables "
        "WHERE table_schema = 'main' AND table_type = 'BASE TABLE' ORDER BY 1").fetchall()}
    existing = {row[0] for row in con.execute(
        "SELECT table_schema || '.' || table_name FROM information_schema.tables").fetchall()}
    return {**app, **{name: rel for name, rel in WAREHOUSE_TABLES.items() if rel in existing}}


def _columns(con, relation):
    return con.execute(f"DESCRIBE SELECT * FROM {relation}").fetchall()


def _pg_type(kind: str) -> str:
    base = re.sub(r"\(.*\)", "", kind).upper()
    return TYPES.get(base, "TEXT") if base not in ("DECIMAL", "HUGEINT") else "NUMERIC"


def publish_postgres(dsn: str, schema: str, db: Path = DB) -> dict:
    schema = _name(schema)
    report = {"changed": {}, "unchanged": []}
    with duckdb.connect(str(db), read_only=True) as source, _connect(dsn) as target:
        tables = served_tables(source)
        with target.cursor() as cursor:
            cursor.execute(sql.SQL("CREATE SCHEMA IF NOT EXISTS {}").format(sql.Identifier(schema)))
            cursor.execute(sql.SQL("SET search_path TO {}").format(sql.Identifier(schema)))
            cursor.execute("CREATE TABLE IF NOT EXISTS snapshot_manifest (table_name text PRIMARY KEY, "
                           "source_size bigint NOT NULL, source_mtime_ns bigint NOT NULL, "
                           "row_count bigint NOT NULL, row_digest text NOT NULL)")
            manifest = dict(cursor.execute("SELECT table_name, row_digest FROM snapshot_manifest").fetchall())
            target.commit()

            staged = {}
            for name, relation in tables.items():
                columns = _columns(source, relation)
                names = [c[0] for c in columns]
                select = f"SELECT {', '.join(chr(34) + n + chr(34) for n in names)} FROM {relation}"
                count, digest = _rows_digest(_chunks(source.execute(select)))
                if manifest.get(name) == digest:
                    report["unchanged"].append(name)
                    continue
                stage = f"{name}__next"
                cursor.execute(sql.SQL("DROP TABLE IF EXISTS {}").format(sql.Identifier(stage)))
                cursor.execute(sql.SQL("CREATE TABLE {} ({})").format(sql.Identifier(stage), sql.SQL(", ").join(
                    sql.SQL("{} {}").format(sql.Identifier(c[0]), sql.SQL(_pg_type(c[1]))) for c in columns)))
                fields = sql.SQL(", ").join(map(sql.Identifier, names))
                with cursor.copy(sql.SQL("COPY {} ({}) FROM STDIN").format(sql.Identifier(stage), fields)) as copy:
                    for row in _chunks(source.execute(select)):
                        copy.write_row(row)
                # ponytail: verifies row count server-side; full read-back digest only on the first publish.
                copied = cursor.execute(sql.SQL("SELECT count(*) FROM {}").format(sql.Identifier(stage))).fetchone()[0]
                if copied != count:
                    raise ValueError(f"{name}: copied {copied} rows, expected {count}")
                target.commit()
                staged[name] = (count, digest)

            # One transaction: swap every changed table, rebuild dependent views, update the manifest.
            if staged:
                for name in staged:
                    cursor.execute(sql.SQL("DROP TABLE IF EXISTS {} CASCADE").format(sql.Identifier(name)))
                    cursor.execute(sql.SQL("ALTER TABLE {} RENAME TO {}").format(
                        sql.Identifier(f"{name}__next"), sql.Identifier(name)))
                    cursor.execute("INSERT INTO snapshot_manifest VALUES (%s, 0, 0, %s, %s) ON CONFLICT (table_name) "
                                   "DO UPDATE SET row_count = excluded.row_count, row_digest = excluded.row_digest",
                                   [name, *staged[name]])
                for view in VIEWS:
                    cursor.execute(view)
                target.commit()
            report["changed"] = {name: count for name, (count, _) in staged.items()}
    return report


def build_sqlite_fallback(db: Path = DB, path: Path = LOCAL_SNAPSHOT) -> dict:
    """Rebuild the read-only fallback from DuckDB; the old file stays until the new one is complete."""
    path = Path(path)
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    os.close(fd)
    os.unlink(temporary)
    counts = {}
    try:
        with duckdb.connect(str(db), read_only=True) as source:
            tables = served_tables(source)
        # In-memory session: warehouse attached read-only, fallback attached writable.
        with duckdb.connect() as con:
            con.execute("INSTALL sqlite; LOAD sqlite")
            con.execute(f"ATTACH '{db}' AS wh (READ_ONLY)")
            con.execute(f"ATTACH '{temporary}' AS fallback (TYPE sqlite)")
            for name, relation in tables.items():
                relation = f"wh.{relation}"
                # Dates/timestamps as ISO text: the format SQLiteReadOnlyStore and pandas already expect.
                columns = _columns(con, relation)
                select = ", ".join(
                    f'CAST("{c[0]}" AS VARCHAR) AS "{c[0]}"' if c[1].upper().startswith(("DATE", "TIMESTAMP"))
                    else f'"{c[0]}"' for c in columns)
                con.execute(f'CREATE TABLE fallback."{name}" AS SELECT {select} FROM {relation}')
                counts[name] = con.execute(f'SELECT count(*) FROM fallback."{name}"').fetchone()[0]
                if counts[name] != con.execute(f"SELECT count(*) FROM {relation}").fetchone()[0]:
                    raise ValueError(f"SQLite fallback count mismatch for {name}")
            con.execute("CREATE TABLE fallback.snapshot_manifest (table_name TEXT PRIMARY KEY, row_count BIGINT)")
            con.executemany("INSERT INTO fallback.snapshot_manifest VALUES (?, ?)", list(counts.items()))
            con.execute("DETACH fallback")
        import sqlite3

        with sqlite3.connect(temporary) as target:
            for view in VIEWS:
                target.execute(view.replace("CREATE OR REPLACE VIEW", "CREATE VIEW", 1))
            target.execute("CREATE INDEX matches_partition ON matches (league, season)")
            target.execute("CREATE INDEX recent_partition ON recent_matches (league, season)")
        os.replace(temporary, path)
        return counts
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def main():
    parser = argparse.ArgumentParser(description="Publish DuckDB to PostgreSQL and the local SQLite fallback")
    parser.add_argument("--skip-postgres", action="store_true")
    parser.add_argument("--skip-sqlite", action="store_true")
    args = parser.parse_args()
    dsn, schema = os.environ.get("FOOTBALL_POSTGRES_DSN"), os.environ.get("FOOTBALL_POSTGRES_SCHEMA", "football_analysis_next")
    if not args.skip_postgres:
        if not dsn:
            parser.error("FOOTBALL_POSTGRES_DSN is not set (or pass --skip-postgres)")
        print(json.dumps({"postgres": publish_postgres(dsn, schema)}), flush=True)
    if not args.skip_sqlite:
        counts = build_sqlite_fallback()
        print(json.dumps({"sqlite": {"tables": len(counts), "rows": sum(counts.values())}}), flush=True)


if __name__ == "__main__":
    main()
