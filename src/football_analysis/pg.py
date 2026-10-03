"""Shared PostgreSQL helpers: safe connections, private schema names, row digests."""

from __future__ import annotations

import hashlib
import json
import os
import re

# DuckDB column type -> PostgreSQL column type for published tables.
TYPES = {
    "BIGINT": "BIGINT", "BOOLEAN": "BOOLEAN", "DATE": "DATE",
    "DOUBLE": "DOUBLE PRECISION", "INTEGER": "INTEGER",
    "TIMESTAMP": "TIMESTAMP", "VARCHAR": "TEXT",
}
MASK = (1 << 256) - 1


def schema_name(name: str | None = None) -> str:
    """A private, lowercase application schema; never Supabase's exposed or system schemas."""
    name = os.environ.get("FOOTBALL_POSTGRES_SCHEMA", "football_analysis") if name is None else name
    if not re.fullmatch(r"[a-z][a-z0-9_]*", name or "") or name in {"public", "auth", "storage"}:
        raise ValueError("FOOTBALL_POSTGRES_SCHEMA must be a private lowercase application schema")
    return name


def driver():
    try:
        import psycopg
    except ImportError as exc:
        raise RuntimeError("Install psycopg: uv sync") from exc
    return psycopg


def connect(dsn: str, **kwargs):
    """Connect with TLS enforced for Supabase hosts and full float precision."""
    psycopg = driver()
    options = psycopg.conninfo.conninfo_to_dict(dsn)
    host = options.get("host", "")
    if (host.endswith(".supabase.co") or host.endswith(".pooler.supabase.com")) and options.get("sslmode") not in {
        "require", "verify-ca", "verify-full",
    }:
        kwargs["sslmode"] = "require"
    connection = psycopg.connect(dsn, **kwargs)
    connection.execute("SET extra_float_digits = 3")
    return connection


def chunks(cursor, size=5000):
    while rows := cursor.fetchmany(size):
        yield from rows


def rows_digest(rows):
    """Order-independent (count, sum/xor of SHA-256) digest of a table's rows."""
    count = total = xor = 0
    for row in rows:
        encoded = json.dumps(row, default=str, ensure_ascii=False, separators=(",", ":"), allow_nan=True)
        value = int.from_bytes(hashlib.sha256(encoded.encode()).digest(), "big")
        count += 1
        total = (total + value) & MASK
        xor ^= value
    return count, f"{total:064x}{xor:064x}"
