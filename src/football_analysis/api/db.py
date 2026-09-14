"""Single-process read-only DuckDB access for the API."""

from __future__ import annotations

import threading
from pathlib import Path

import duckdb
import pandas as pd


class ReadOnlyStore:
    """One application-owned DuckDB connection opened read-only."""

    def __init__(self, path: Path):
        self.path = Path(path)
        if not self.path.exists():
            raise FileNotFoundError(f"Database is missing: {self.path}")
        self._con = duckdb.connect(str(self.path), read_only=True)
        self._lock = threading.Lock()

    def tables(self) -> set[str]:
        frame = self.query("SHOW TABLES")
        if frame.empty:
            return set()
        return set(frame.iloc[:, 0].astype(str))

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
