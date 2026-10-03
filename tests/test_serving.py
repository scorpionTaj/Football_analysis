"""Serving-path integration tests: incremental PostgreSQL publish, SQLite fallback, API parity.

Uses TEST_POSTGRES_DSN when set, otherwise starts a temporary local PostgreSQL server when
`initdb`/`pg_ctl` are available (skipped otherwise).
"""

from __future__ import annotations

import os
import random
import shutil
import subprocess
import uuid
from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient

from football_analysis.api.app import create_app
from football_analysis.api.db import PostgresReadOnlyStore, ReadOnlyStore
from football_analysis.ingest import connect
from football_analysis.pg import connect as pg_connect, schema_name
from football_analysis.publish import build_sqlite_fallback, publish_postgres


@pytest.fixture(scope="module")
def postgres_server(tmp_path_factory):
    psycopg = pytest.importorskip("psycopg")
    supplied = os.environ.get("TEST_POSTGRES_DSN")
    if supplied:
        yield supplied
        return
    if not (shutil.which("initdb") and shutil.which("pg_ctl")):
        pytest.skip("No local PostgreSQL server binaries")
    root = tmp_path_factory.mktemp("postgres")
    data = root / "data"
    socket = root / "socket"
    socket.mkdir()
    port = random.randrange(20000, 50000)
    try:
        subprocess.run(
            ["initdb", "-D", str(data), "-A", "trust", "--no-instructions"],
            check=True, capture_output=True, timeout=30,
        )
        subprocess.run(
            ["pg_ctl", "-D", str(data), "-o", f"-k {socket} -h '' -p {port}",
             "-l", str(root / "postgres.log"), "-w", "start"],
            check=True, capture_output=True, timeout=30,
        )
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
        pytest.skip(f"Temporary PostgreSQL could not start: {exc}")
    try:
        yield psycopg.conninfo.make_conninfo("", host=str(socket), port=port, dbname="postgres")
    finally:
        subprocess.run(["pg_ctl", "-D", str(data), "-m", "immediate", "stop"], capture_output=True, timeout=30)


@pytest.fixture
def match_db(tmp_path):
    path = tmp_path / "matches.duckdb"
    future = date.today() + timedelta(days=2)
    with connect(path) as con:
        con.execute("""
            INSERT INTO matches
                (league, season, match_date, home_team, away_team, home_goals, away_goals)
            VALUES
                ('SP1', 2024, '2024-08-01', 'Barcelona', 'Real Madrid', 2, 1),
                ('SP1', 2024, '2024-08-02', 'Ath Madrid', 'Barcelona', 1, 0),
                ('SP1', 2024, '2024-08-03', 'Real Madrid', 'Ath Madrid', 0, 0)
        """)
        con.execute("""
            INSERT INTO recent_matches
                (league, season, match_date, home_team, away_team, home_goals, away_goals, source, fetched_at)
            VALUES
                ('SP1', 2024, '2024-08-01', 'Barcelona', 'Real Madrid', 2, 1, 'recent', current_timestamp),
                ('E0', 2024, '2024-08-01', 'Arsenal', 'Chelsea', 1, 0, 'recent', current_timestamp)
        """)
        con.execute("""
            INSERT INTO recent_events
                (event_id, league, season, match_date, home_team, away_team, event_kind, source, fetched_at)
            VALUES
                ('fixture-old', 'SP1', 2024, ?, 'Barcelona', 'Valencia', 'next', 'next', current_timestamp),
                ('fixture-new', 'SP1', 2024, ?, 'Barcelona', 'Valencia', 'fixture', 'fixture', current_timestamp),
                ('completed-fixture', 'SP1', 2024, ?, 'Barcelona', 'Real Madrid', 'fixture', 'fixture', current_timestamp)
        """, [future + timedelta(days=5), future, future])
    return path


def _body(response):
    assert response.status_code == 200, response.text
    body = response.json()
    body.pop("source")
    body.pop("generated_at", None)
    return body


def test_publish_swaps_only_changed_tables(match_db, postgres_server, tmp_path):
    from football_analysis.api.db import SQLiteReadOnlyStore

    schema = "publish_test_" + uuid.uuid4().hex
    try:
        first = publish_postgres(postgres_server, schema, match_db)
        assert "matches" in first["changed"] and not first["unchanged"]
        assert publish_postgres(postgres_server, schema, match_db)["changed"] == {}
        with connect(match_db) as con:
            con.execute("UPDATE matches SET home_goals = 9 WHERE league = 'SP1' AND season = 2024 "
                        "AND home_team = (SELECT min(home_team) FROM matches WHERE league = 'SP1')")
        assert set(publish_postgres(postgres_server, schema, match_db)["changed"]) == {"matches"}
        with PostgresReadOnlyStore(postgres_server, schema) as store:
            assert store.scalar("SELECT max(home_goals) FROM matches") == 9
            assert store.scalar("SELECT count(*) FROM team_seasons") > 0  # views rebuilt after swap
        local = tmp_path / "fallback.sqlite3"
        counts = build_sqlite_fallback(match_db, local)
        with SQLiteReadOnlyStore(local) as store:
            assert store.scalar("SELECT count(*) FROM matches") == counts["matches"]
            assert store.scalar("SELECT count(*) FROM team_seasons") > 0
    finally:
        with pg_connect(postgres_server, autocommit=True) as conn:
            conn.execute(f"DROP SCHEMA IF EXISTS {schema} CASCADE")


def test_sqlite_read_fallback_preserves_api_data(match_db, postgres_server, monkeypatch):
    from football_analysis.api.db import SQLiteReadOnlyStore

    local = match_db.with_suffix(".sqlite3")
    counts = build_sqlite_fallback(match_db, local)
    assert counts["matches"] == 3
    monkeypatch.setenv("FOOTBALL_API_READ_BACKEND", "postgres")
    monkeypatch.delenv("FOOTBALL_POSTGRES_DSN", raising=False)
    app = create_app(match_db)
    assert isinstance(app.state.store, SQLiteReadOnlyStore)
    with TestClient(app) as client:
        for route in ("/api/v1/catalog", "/api/v1/teams?competition=SP1&season=2024",
                      "/api/v1/matches?competition=SP1&season=2024",
                      "/api/v1/overview?competition=SP1&season=2024"):
            response = client.get(route)
            assert response.status_code == 200, (route, response.text)
        assert len(client.get("/api/v1/matches?competition=SP1&season=2024").json()["matches"]) == 4
    import psycopg

    monkeypatch.setenv("FOOTBALL_POSTGRES_DSN", postgres_server)

    def unavailable(*_args, **_kwargs):
        raise psycopg.OperationalError("offline")

    monkeypatch.setattr("football_analysis.pg.connect", unavailable)
    outage_app = create_app(match_db)
    assert isinstance(outage_app.state.store, SQLiteReadOnlyStore)
    outage_app.state.store.close()


def test_schema_name_rejects_exposed_schemas():
    for name in ("public", "auth", "Mixed-Case"):
        with pytest.raises(ValueError, match="private"):
            schema_name(name)


def test_published_snapshot_supports_shared_api_queries(match_db, postgres_server):
    from football_analysis.api import queries

    schema = "snapshot_test_" + uuid.uuid4().hex
    publish_postgres(postgres_server, schema, match_db)
    with ReadOnlyStore(match_db) as duck, PostgresReadOnlyStore(postgres_server, schema) as postgres:
        for build in (
            lambda store: queries.catalog(store),
            lambda store: queries.list_teams(store, "SP1", 2024),
            lambda store: queries.list_matches(store, "SP1", 2024),
            lambda store: queries.quality(store),
        ):
            pg_body = build(postgres).model_dump(mode="json")
            duck_body = build(duck).model_dump(mode="json")
            pg_body.pop("source", None)
            duck_body.pop("source", None)
            assert pg_body == duck_body


def test_published_snapshot_api_switch(match_db, postgres_server, monkeypatch):
    import psycopg

    schema = "snapshot_test_" + uuid.uuid4().hex
    with psycopg.connect(postgres_server) as conn:
        conn.execute(f'CREATE SCHEMA "{schema}"')
    with pytest.raises(ValueError, match="no verified snapshot"):
        PostgresReadOnlyStore(postgres_server, schema)
    with psycopg.connect(postgres_server) as conn:
        conn.execute(f'DROP SCHEMA "{schema}"')
    publish_postgres(postgres_server, schema, match_db)
    duck_app = create_app(match_db)
    monkeypatch.setenv("FOOTBALL_API_READ_BACKEND", "postgres")
    monkeypatch.setenv("FOOTBALL_POSTGRES_DSN", postgres_server)
    monkeypatch.setenv("FOOTBALL_POSTGRES_SCHEMA", schema)
    pg_app = create_app(match_db)
    try:
        duck = TestClient(duck_app)
        pg = TestClient(pg_app)
        for path, params in (
            ("/api/v1/catalog", {}),
            ("/api/v1/teams", {"competition": "SP1", "season": 2024}),
            ("/api/v1/matches", {"competition": "SP1", "season": 2024}),
            ("/api/v1/shots", {"competition": "SP1", "season": 2024}),
            ("/api/v1/event-details", {}),
            ("/api/v1/predictions", {}),
            ("/api/v1/players", {}),
            ("/api/v1/standings", {"competition": "SP1", "season": 2024}),
            ("/api/v1/overview", {"competition": "SP1", "season": 2024}),
            ("/api/v1/transfers", {}),
            ("/api/v1/tournaments/UCL/2024", {}),
            ("/api/v1/match-detail", {"competition": "SP1", "season": 2024,
                                       "match_date": "2024-08-01", "home": "Barcelona", "away": "Real Madrid"}),
            ("/api/v1/quality", {}),
        ):
            assert _body(pg.get(path, params=params)) == _body(duck.get(path, params=params))
        assert _body(pg.post("/api/v1/analysis", json={"competitions": ["SP1"], "seasons": [2024]})) == _body(
            duck.post("/api/v1/analysis", json={"competitions": ["SP1"], "seasons": [2024]})
        )
    finally:
        pg_app.state.store.close()
        duck_app.state.store.close()


@pytest.mark.skipif(not os.environ.get("FOOTBALL_VERIFY_FULL_SNAPSHOT"), reason="large local data check is opt-in")
def test_full_local_snapshot_against_temporary_postgres(postgres_server, monkeypatch):
    from football_analysis.config import DB

    if not DB.exists():
        pytest.skip("No local DuckDB source snapshot")
    schema = "full_snapshot_test_" + uuid.uuid4().hex
    counts = publish_postgres(postgres_server, schema, DB)["changed"]
    assert sum(counts.values()) > 0
    with PostgresReadOnlyStore(postgres_server, schema) as store:
        assert store.scalar("SELECT count(*) FROM matches") == counts["matches"]
        assert store.scalar("SELECT count(*) FROM event_lineups") == counts["event_lineups"]
    duck_app = create_app(DB)
    monkeypatch.setenv("FOOTBALL_API_READ_BACKEND", "postgres")
    monkeypatch.setenv("FOOTBALL_POSTGRES_DSN", postgres_server)
    monkeypatch.setenv("FOOTBALL_POSTGRES_SCHEMA", schema)
    pg_app = create_app(DB)
    try:
        duck = TestClient(duck_app)
        pg = TestClient(pg_app)
        for path, params in (
            ("/api/v1/catalog", {}),
            ("/api/v1/matches", {"competition": "E0", "season": 2026, "limit": 20}),
            ("/api/v1/predictions", {}),
            ("/api/v1/players", {"limit": 20}),
            ("/api/v1/transfers", {"limit": 20}),
            ("/api/v1/tournaments/UCL/2024", {}),
        ):
            assert _body(pg.get(path, params=params)) == _body(duck.get(path, params=params)), path
    finally:
        pg_app.state.store.close()
        duck_app.state.store.close()
