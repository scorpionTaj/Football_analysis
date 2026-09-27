"""One-time, verified DuckDB snapshot copy into a private PostgreSQL schema."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
from importlib.resources import files
from pathlib import Path

import duckdb
import psycopg
from psycopg import sql

from .api.postgres_matches import _connect
from .config import DB


TYPES = {
    "BIGINT": "BIGINT", "BOOLEAN": "BOOLEAN", "DATE": "DATE",
    "DOUBLE": "DOUBLE PRECISION", "INTEGER": "INTEGER",
    "TIMESTAMP": "TIMESTAMP", "VARCHAR": "TEXT",
}
MASK = (1 << 256) - 1


def _name(value: str) -> str:
    if not re.fullmatch(r"[a-z][a-z0-9_]*", value) or value in {"public", "auth", "storage"}:
        raise ValueError("Use a private lowercase PostgreSQL schema name")
    return value


def _rows_digest(rows):
    count = total = xor = 0
    for row in rows:
        encoded = json.dumps(row, default=str, ensure_ascii=False, separators=(",", ":"), allow_nan=True)
        value = int.from_bytes(hashlib.sha256(encoded.encode()).digest(), "big")
        count += 1
        total = (total + value) & MASK
        xor ^= value
    return count, f"{total:064x}{xor:064x}"


def _chunks(cursor, size=5000):
    while rows := cursor.fetchmany(size):
        yield from rows


def _tables(source):
    return [
        row[0] for row in source.execute(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema = current_schema() AND table_type = 'BASE TABLE' "
            "ORDER BY table_name"
        ).fetchall()
    ]


def _source_columns(source, table):
    return source.execute("SELECT * FROM pragma_table_info(?)", [table]).fetchall()


def _create_extra_table(cursor, source, table):
    columns = _source_columns(source, table)
    definitions = []
    primary = []
    for _, name, kind, required, default, is_primary in columns:
        if kind not in TYPES:
            raise ValueError(f"Unsupported source type {kind} in {table}.{name}")
        definition = sql.SQL("{} {}").format(sql.Identifier(name), sql.SQL(TYPES[kind]))
        if required:
            definition += sql.SQL(" NOT NULL")
        if default and default.lower() == "current_timestamp":
            definition += sql.SQL(" DEFAULT CURRENT_TIMESTAMP")
        definitions.append(definition)
        if is_primary:
            primary.append(sql.Identifier(name))
    if primary:
        definitions.append(sql.SQL("PRIMARY KEY ({})").format(sql.SQL(", ").join(primary)))
    cursor.execute(sql.SQL("CREATE TABLE {} ({})").format(
        sql.Identifier(table), sql.SQL(", ").join(definitions),
    ))


def _create_schema(cursor, source, schema):
    cursor.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(schema)))
    cursor.execute(sql.SQL("REVOKE ALL ON SCHEMA {} FROM PUBLIC").format(sql.Identifier(schema)))
    cursor.execute(sql.SQL("SET LOCAL search_path TO {}").format(sql.Identifier(schema)))
    source_schema = files("football_analysis").joinpath("schema.sql").read_text()
    source_schema = re.sub(r"\bDOUBLE\b", "DOUBLE PRECISION", source_schema)
    for statement in source_schema.split(";"):
        if statement.strip():
            cursor.execute(statement)
    existing = {
        row[0] for row in cursor.execute(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema = %s AND table_type = 'BASE TABLE'", [schema],
        ).fetchall()
    }
    for table in _tables(source):
        if table not in existing:
            _create_extra_table(cursor, source, table)
    cursor.execute(
        "CREATE TABLE snapshot_manifest ("
        "table_name text PRIMARY KEY, source_size bigint NOT NULL, "
        "source_mtime_ns bigint NOT NULL, row_count bigint NOT NULL, "
        "row_digest text NOT NULL)"
    )


def _verify_existing(cursor, source, schema, stat):
    cursor.execute(sql.SQL("SET LOCAL search_path TO {}").format(sql.Identifier(schema)))
    try:
        records = cursor.execute(
            "SELECT table_name, source_size, source_mtime_ns, row_count, row_digest "
            "FROM snapshot_manifest"
        ).fetchall()
    except psycopg.errors.UndefinedTable as exc:
        raise ValueError("Target schema exists without a completed snapshot manifest") from exc
    expected = {row[0]: row[1:] for row in records}
    if set(expected) != set(_tables(source)):
        raise ValueError("Target schema does not match source tables; use a new private schema")
    if any(row[:2] != (stat.st_size, stat.st_mtime_ns) for row in expected.values()):
        raise ValueError("Source changed since publication; use a new private schema")
    for table, (_, _, count, digest) in expected.items():
        names = [row[1] for row in _source_columns(source, table)]
        fields = sql.SQL(", ").join(map(sql.Identifier, names))
        cursor.execute(sql.SQL("SELECT {} FROM {}").format(fields, sql.Identifier(table)))
        if _rows_digest(_chunks(cursor)) != (count, digest):
            raise ValueError(f"Target table {table} failed verification")
    return {table: values[2] for table, values in expected.items()}


def copy_snapshot(source_path: Path, dsn: str, schema: str = "football_analysis_next") -> dict[str, int]:
    """Copy without replacing existing schemas; failed attempts roll back entirely."""
    schema = _name(schema)
    if not dsn:
        raise ValueError("FOOTBALL_POSTGRES_DSN is required")
    source_path = Path(source_path)
    stat = source_path.stat()
    with duckdb.connect(str(source_path), read_only=True) as source:
        with _connect(dsn) as target:
            with target.cursor() as cursor:
                exists = cursor.execute(
                    "SELECT 1 FROM pg_namespace WHERE nspname = %s", [schema],
                ).fetchone()
                if exists:
                    return _verify_existing(cursor, source, schema, stat)
                _create_schema(cursor, source, schema)
                counts = {}
                for table in _tables(source):
                    names = [row[1] for row in _source_columns(source, table)]
                    fields = sql.SQL(", ").join(map(sql.Identifier, names))
                    statement = sql.SQL("COPY {} ({}) FROM STDIN").format(
                        sql.Identifier(table), fields,
                    )
                    quoted_table = '"' + table.replace('"', '""') + '"'
                    reader = source.execute(f"SELECT * FROM {quoted_table}")
                    count = total = xor = 0
                    with cursor.copy(statement) as writer:
                        for row in _chunks(reader):
                            writer.write_row(row)
                            encoded = json.dumps(row, default=str, ensure_ascii=False, separators=(",", ":"), allow_nan=True)
                            value = int.from_bytes(hashlib.sha256(encoded.encode()).digest(), "big")
                            count += 1
                            total = (total + value) & MASK
                            xor ^= value
                    digest = f"{total:064x}{xor:064x}"
                    cursor.execute(sql.SQL("SELECT {} FROM {}").format(fields, sql.Identifier(table)))
                    if _rows_digest(_chunks(cursor)) != (count, digest):
                        raise ValueError(f"Snapshot verification failed for {table}")
                    cursor.execute(
                        "INSERT INTO snapshot_manifest VALUES (%s, %s, %s, %s, %s)",
                        [table, stat.st_size, stat.st_mtime_ns, count, digest],
                    )
                    counts[table] = count
                return counts


def main():
    parser = argparse.ArgumentParser(description="Copy and verify a DuckDB snapshot in a private PostgreSQL schema")
    parser.add_argument("--source", type=Path, default=DB)
    parser.add_argument("--schema", default=os.environ.get("FOOTBALL_POSTGRES_SCHEMA", "football_analysis_next"))
    parser.add_argument("--dsn", default=os.environ.get("FOOTBALL_POSTGRES_DSN"))
    args = parser.parse_args()
    counts = copy_snapshot(args.source, args.dsn, args.schema)
    print(json.dumps({"schema": args.schema, "tables": len(counts), "rows": sum(counts.values())}))


if __name__ == "__main__":
    main()
