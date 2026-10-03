"""Single-process read-only DuckDB access for the API."""

from __future__ import annotations

import threading
import sqlite3
from datetime import datetime
from pathlib import Path
from uuid import uuid4

import duckdb
import pandas as pd


class ReadOnlyStore:
    """One application-owned DuckDB connection opened read-only."""

    def __init__(self, path: Path):
        self.path = Path(path)
        if not self.path.exists():
            raise FileNotFoundError(f"Database is missing: {self.path}")
        self._con = duckdb.connect(str(self.path), read_only=True)
        # Serving stores are flat; in DuckDB the warehouse layers live in their own schemas.
        schemas = {row[0] for row in self._con.execute("SELECT schema_name FROM information_schema.schemata").fetchall()}
        self._con.execute(f"SET search_path = '{','.join(s for s in ('main', 'marts', 'ml') if s in schemas)}'")
        self._lock = threading.Lock()
        self.opened_at = datetime.now().replace(microsecond=0)
        # A refresh closes this read snapshot and opens a new one. The token
        # covers every table, including media and reference data, without a
        # query or a fragile list of per-table timestamps on each cache hit.
        self.generation = uuid4().hex

    def tables(self) -> set[str]:
        frame = self.query("SELECT table_name FROM information_schema.tables "
                           "WHERE table_schema IN ('main', 'marts', 'ml')")
        return set(frame.table_name.astype(str))

    def query(self, sql: str, params: list | tuple | None = None) -> pd.DataFrame:
        with self._lock:
            if params:
                return self._con.execute(sql, list(params)).df()
            return self._con.execute(sql).df()

    def scalar(self, sql: str, params: list | tuple | None = None):
        frame = self.query(sql, params)
        if frame.empty:
            return None
        return frame.iloc[0, 0]

    def close(self) -> None:
        with self._lock:
            self._con.close()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()


class PostgresReadOnlyStore:
    """Read the verified snapshot through the API's existing DataFrame queries."""

    def __init__(self, dsn: str, schema: str):
        from football_analysis.pg import connect as _connect, driver as _driver, schema_name as _schema_name

        if not dsn:
            raise ValueError("FOOTBALL_POSTGRES_DSN is required")
        psycopg = _driver()
        self.schema = _schema_name(schema)
        self.path = f"postgresql:{self.schema}"
        self._con = _connect(dsn, autocommit=True, connect_timeout=5)
        self._con.execute(psycopg.sql.SQL("SET search_path TO {}").format(psycopg.sql.Identifier(self.schema)))
        self._con.execute("SET SESSION CHARACTERISTICS AS TRANSACTION READ ONLY")
        self._lock = threading.Lock()
        self.opened_at = datetime.now().replace(microsecond=0)
        self.generation = uuid4().hex
        self._tables = set(self.query(
            "SELECT table_name FROM information_schema.tables WHERE table_schema = ?", [self.schema],
        ).table_name.astype(str))
        if "snapshot_manifest" not in self._tables:
            self._con.close()
            raise ValueError("PostgreSQL schema has no verified snapshot; run football-migrate-postgres first")

    def tables(self) -> set[str]:
        return set(self._tables)

    def query(self, sql: str, params: list | tuple | None = None) -> pd.DataFrame:
        sql = sql.replace(
            "try_cast(minute AS INTEGER)",
            "CASE WHEN minute ~ '^[0-9]+$' THEN minute::integer END",
        ).replace("?", "%s")
        with self._lock:
            with self._con.cursor() as cursor:
                cursor.execute(sql, params or ())
                return pd.DataFrame(cursor.fetchall(), columns=[column.name for column in cursor.description])

    def scalar(self, sql: str, params: list | tuple | None = None):
        frame = self.query(sql, params)
        return None if frame.empty else frame.iloc[0, 0]

    def close(self) -> None:
        with self._lock:
            self._con.close()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()


class SQLiteReadOnlyStore:
    """Local, count-verified snapshot used only when PostgreSQL is unreachable."""

    def __init__(self, path: Path):
        self.path = Path(path)
        if not self.path.exists():
            raise FileNotFoundError(f"Local snapshot is missing: {self.path}")
        self._con = sqlite3.connect(self.path.resolve().as_uri() + "?mode=ro", uri=True, check_same_thread=False)
        self._lock = threading.Lock()
        self.opened_at = datetime.now().replace(microsecond=0)
        self.generation = uuid4().hex
        self._tables = {row[0] for row in self._con.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )}
        if "snapshot_manifest" not in self._tables:
            self.close()
            raise ValueError("Local SQLite snapshot is not verified")

    def tables(self) -> set[str]:
        return set(self._tables)

    def query(self, sql: str, params: list | tuple | None = None) -> pd.DataFrame:
        sql = sql.replace("try_cast(minute AS INTEGER)", "CAST(minute AS INTEGER)")
        sql = sql.replace(" ILIKE ", " LIKE ")
        with self._lock:
            return pd.read_sql_query(sql, self._con, params=params or ())

    def scalar(self, sql: str, params: list | tuple | None = None):
        frame = self.query(sql, params)
        return None if frame.empty else frame.iloc[0, 0]

    def close(self) -> None:
        with self._lock:
            self._con.close()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()
