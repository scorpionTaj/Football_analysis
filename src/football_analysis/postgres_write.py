"""Writable PostgreSQL connection for the existing ingestion commands."""

from __future__ import annotations

import re

import numpy as np
import pandas as pd
from psycopg import sql

from .api.postgres_matches import _connect, _schema_name


_TARGETS = {
    "incoming": "matches",
    "incoming_elo": "elo_ratings",
    "incoming_shots": "shot_efficiency_cache",
    "incoming_recent": "recent_matches",
    "incoming_events": "recent_events",
    "incoming_fixtures": "recent_events",
    "incoming_open_fixtures": "recent_events",
    "incoming_cup_events": "recent_events",
    "incoming_cup_matches": "tournament_matches",
    "incoming_tournament": "tournament_matches",
    "incoming_reference": "reference_standings",
    "incoming_open_stats": "open_player_stats",
    "incoming_model": "prediction_models",
    "incoming_predictions": "match_predictions",
}


def _value(value):
    if value is None or pd.isna(value):
        return None
    if isinstance(value, pd.Timestamp):
        return value.to_pydatetime()
    if isinstance(value, np.generic):
        return value.item()
    return value


class PostgresWriteStore:
    """Expose the small connection surface shared by the synchronizers."""

    def __init__(self, dsn: str, schema: str):
        if not dsn:
            raise ValueError("FOOTBALL_POSTGRES_DSN is required for PostgreSQL writes")
        self.schema = _schema_name(schema)
        self._con = _connect(dsn, autocommit=True)
        self._con.execute(sql.SQL("SET search_path TO {}").format(sql.Identifier(self.schema)))
        self._cursor = self._con.cursor()
        if not self._cursor.execute("SELECT to_regclass('snapshot_manifest')").fetchone()[0]:
            self.close()
            raise ValueError("PostgreSQL snapshot is missing; run football-migrate-postgres first")

    def execute(self, statement: str, params=None):
        if statement.strip().upper() == "SHOW TABLES":
            statement = "SELECT table_name FROM information_schema.tables WHERE table_schema = current_schema()"
        statement = statement.replace("?", "%s")
        statement = re.sub(r"\bINSERT OR IGNORE INTO\b", "INSERT INTO", statement, flags=re.I)
        if "incoming_forecast_history" in statement and statement.lstrip().upper().startswith("INSERT INTO"):
            statement += " ON CONFLICT DO NOTHING"
        self._cursor.execute(statement, params or ())
        return self

    def sql(self, statement: str):
        return self.execute(statement)

    def fetchone(self):
        return self._cursor.fetchone()

    def fetchall(self):
        return self._cursor.fetchall()

    def df(self):
        return pd.DataFrame(self.fetchall(), columns=[column.name for column in self._cursor.description])

    def register(self, name: str, frame: pd.DataFrame):
        if not re.fullmatch(r"incoming_[a-z_]+|incoming", name):
            raise ValueError("Unexpected temporary table name")
        target = _TARGETS.get(name, name.removeprefix("incoming_"))
        with self._con.cursor() as cursor:
            cursor.execute(sql.SQL("CREATE TEMP TABLE {} AS SELECT * FROM {} LIMIT 0").format(
                sql.Identifier(name), sql.Identifier(target),
            ))
            columns = sql.SQL(", ").join(map(sql.Identifier, frame.columns))
            with cursor.copy(sql.SQL("COPY {} ({}) FROM STDIN").format(sql.Identifier(name), columns)) as writer:
                for row in frame.itertuples(index=False, name=None):
                    writer.write_row(tuple(_value(value) for value in row))

    def unregister(self, name: str):
        self._con.execute(sql.SQL("DROP TABLE IF EXISTS pg_temp.{}").format(sql.Identifier(name)))

    def close(self):
        self._cursor.close()
        self._con.close()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()
