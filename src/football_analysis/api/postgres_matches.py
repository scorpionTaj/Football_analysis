"""Optional, versioned PostgreSQL read model for one match partition at a time."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from football_analysis.api.db import ReadOnlyStore
from football_analysis.api.queries import load_match_source_rows
from football_analysis.config import DB


SCHEMA_VERSION = 1


def _schema_name(name: str | None = None) -> str:
    if name is None:
        name = os.environ.get("FOOTBALL_POSTGRES_SCHEMA", "football_analysis")
    if not name or name in {"public", "auth", "storage"}:
        raise ValueError("FOOTBALL_POSTGRES_SCHEMA must be a private application schema")
    return name


class PartitionUnavailable(RuntimeError):
    """The requested partition is absent or fails its integrity check."""


@dataclass(frozen=True)
class Partition:
    rows: pd.DataFrame
    version: int
    row_count: int
    checksum: str


def _driver():
    try:
        import psycopg
    except ImportError as exc:
        raise RuntimeError("Install the postgres extra: uv sync --extra postgres") from exc
    return psycopg


def _connect(dsn: str, **kwargs):
    psycopg = _driver()
    options = psycopg.conninfo.conninfo_to_dict(dsn)
    host = options.get("host", "")
    if (host.endswith(".supabase.co") or host.endswith(".pooler.supabase.com")) and options.get("sslmode") not in {
        "require", "verify-ca", "verify-full",
    }:
        kwargs["sslmode"] = "require"
    connection = psycopg.connect(dsn, **kwargs)
    connection.execute("SET extra_float_digits = 3")
    return connection


def _encode_rows(frame: pd.DataFrame) -> list[dict]:
    # Pandas converts dates and nulls to JSON values consistently for both drivers.
    return json.loads(frame.to_json(orient="records", date_format="iso"))


def _checksum(rows: list[dict]) -> str:
    payload = json.dumps(rows, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode()).hexdigest()


def _stored_rows(cur, competition: str, season: int) -> list[dict]:
    cur.execute(
        "SELECT ordinal, payload FROM match_read_rows "
        "WHERE competition = %s AND season = %s ORDER BY ordinal",
        (competition, season),
    )
    records = cur.fetchall()
    if [record[0] for record in records] != list(range(len(records))):
        raise PartitionUnavailable("Match partition has missing or duplicate ordinals")
    return [record[1] for record in records]


def _ensure_schema(cur) -> None:
    cur.execute("""
        CREATE TABLE IF NOT EXISTS match_read_partitions (
            competition text NOT NULL,
            season integer NOT NULL,
            schema_version integer NOT NULL,
            version bigint NOT NULL,
            row_count integer NOT NULL,
            checksum text NOT NULL,
            published_at timestamptz NOT NULL DEFAULT now(),
            PRIMARY KEY (competition, season)
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS match_read_rows (
            competition text NOT NULL,
            season integer NOT NULL,
            ordinal integer NOT NULL,
            payload jsonb NOT NULL,
            PRIMARY KEY (competition, season, ordinal)
        )
    """)


def publish_partition(database_path: Path, dsn: str, competition: str, season: int) -> Partition:
    """Atomically replace one scoped snapshot, or leave an identical version intact."""
    if not competition or not dsn:
        raise ValueError("A competition and PostgreSQL DSN are required")
    with ReadOnlyStore(database_path) as store:
        frame = load_match_source_rows(store)
    if frame.empty:
        frame = pd.DataFrame()
    else:
        frame = frame[(frame.competition == competition) & (frame.season == season)].reset_index(drop=True)
    rows = _encode_rows(frame)
    checksum = _checksum(rows)
    psycopg = _driver()
    with _connect(dsn) as conn:
        with conn.cursor() as cur:
            schema = psycopg.sql.Identifier(_schema_name())
            cur.execute(psycopg.sql.SQL("CREATE SCHEMA IF NOT EXISTS {}").format(schema))
            cur.execute(psycopg.sql.SQL("SET LOCAL search_path TO {}").format(schema))
            _ensure_schema(cur)
            cur.execute("SELECT pg_advisory_xact_lock(hashtext(%s), %s)", (competition, season))
            cur.execute(
                "SELECT schema_version, version, row_count, checksum FROM match_read_partitions "
                "WHERE competition = %s AND season = %s",
                (competition, season),
            )
            previous = cur.fetchone()
            if previous and previous[0] == SCHEMA_VERSION and previous[2:] == (len(rows), checksum):
                try:
                    current = _stored_rows(cur, competition, season)
                except PartitionUnavailable:
                    current = None
                if current is not None and len(current) == len(rows) and _checksum(current) == checksum:
                    return Partition(frame, previous[1], len(rows), checksum)
            version = (previous[1] + 1) if previous else 1
            cur.execute(
                "DELETE FROM match_read_rows WHERE competition = %s AND season = %s",
                (competition, season),
            )
            from psycopg.types.json import Jsonb
            if rows:
                cur.executemany(
                    "INSERT INTO match_read_rows (competition, season, ordinal, payload) "
                    "VALUES (%s, %s, %s, %s)",
                    [(competition, season, index, Jsonb(row)) for index, row in enumerate(rows)],
                )
            copied = _stored_rows(cur, competition, season)
            if len(copied) != len(rows) or _checksum(copied) != checksum:
                raise PartitionUnavailable("PostgreSQL copy failed row-count/checksum verification")
            cur.execute("""
                INSERT INTO match_read_partitions
                    (competition, season, schema_version, version, row_count, checksum)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (competition, season) DO UPDATE SET
                    schema_version = EXCLUDED.schema_version,
                    version = EXCLUDED.version,
                    row_count = EXCLUDED.row_count,
                    checksum = EXCLUDED.checksum,
                    published_at = now()
            """, (competition, season, SCHEMA_VERSION, version, len(rows), checksum))
    return Partition(frame, version, len(rows), checksum)


def read_partition(dsn: str, competition: str, season: int) -> Partition:
    psycopg = _driver()
    try:
        with _connect(dsn) as conn:
            with conn.cursor() as cur:
                cur.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
                cur.execute(psycopg.sql.SQL("SET LOCAL search_path TO {}").format(psycopg.sql.Identifier(_schema_name())))
                cur.execute(
                    "SELECT schema_version, version, row_count, checksum FROM match_read_partitions "
                    "WHERE competition = %s AND season = %s",
                    (competition, season),
                )
                metadata = cur.fetchone()
                if metadata is None:
                    raise PartitionUnavailable(f"Match partition {competition}/{season} is not published")
                schema_version, version, row_count, checksum = metadata
                if schema_version != SCHEMA_VERSION or version < 1:
                    raise PartitionUnavailable("Match partition schema version is unsupported")
                rows = _stored_rows(cur, competition, season)
                if len(rows) != row_count or _checksum(rows) != checksum:
                    raise PartitionUnavailable("Match partition failed row-count/checksum verification")
    except psycopg.Error as exc:
        raise PartitionUnavailable("PostgreSQL match read model is unavailable") from exc
    return Partition(pd.DataFrame(rows), version, row_count, checksum)


def main() -> None:
    parser = argparse.ArgumentParser(description="Publish one DuckDB match partition to PostgreSQL")
    parser.add_argument("competition")
    parser.add_argument("season", type=int)
    parser.add_argument("--database", type=Path, default=DB)
    parser.add_argument("--dsn", default=os.environ.get("FOOTBALL_POSTGRES_DSN"))
    args = parser.parse_args()
    result = publish_partition(args.database, args.dsn, args.competition, args.season)
    print(json.dumps({
        "competition": args.competition, "season": args.season,
        "version": result.version, "row_count": result.row_count, "checksum": result.checksum,
    }))


if __name__ == "__main__":
    main()
