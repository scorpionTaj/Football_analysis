"""Integration coverage for the optional match read model.

Uses TEST_POSTGRES_DSN when set, otherwise starts a local temporary server if
PostgreSQL binaries and the optional psycopg dependency are available.
"""

from __future__ import annotations

import os
import random
import shutil
import subprocess
import uuid
from datetime import date, timedelta

import pytest
from fastapi import HTTPException, Request
from fastapi.testclient import TestClient

from football_analysis.api.app import create_app
from football_analysis.api.db import PostgresReadOnlyStore, ReadOnlyStore
from football_analysis.api.postgres_matches import Partition, PartitionUnavailable, _connect, _encode_rows, _schema_name, publish_partition, read_partition
from football_analysis.api.queries import list_matches, load_match_source_rows
from football_analysis.ingest import connect
from football_analysis.postgres_snapshot import copy_snapshot
from football_analysis.postgres_write import PostgresWriteStore
from football_analysis.sqlite_snapshot import refresh_local_snapshot


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
def pg_dsn(postgres_server, monkeypatch):
    import psycopg

    schema = "match_test_" + uuid.uuid4().hex
    with psycopg.connect(postgres_server, autocommit=True) as conn:
        conn.execute(f"CREATE SCHEMA {schema}")
    monkeypatch.setenv("FOOTBALL_POSTGRES_SCHEMA", schema)
    dsn = psycopg.conninfo.make_conninfo(postgres_server, options=f"-c search_path={schema}")
    try:
        yield dsn
    finally:
        with psycopg.connect(postgres_server, autocommit=True) as conn:
            conn.execute(f"DROP SCHEMA {schema} CASCADE")


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


def test_postgres_ingest_writes_verified_snapshot(match_db, postgres_server, monkeypatch, tmp_path):
    from football_analysis.adapters import Batch
    from football_analysis.ingest import ingest
    from football_analysis.api.db import PostgresReadOnlyStore
    from football_analysis.transfers import sync_transfers

    schema = "ingest_test_" + uuid.uuid4().hex
    copy_snapshot(match_db, postgres_server, schema)
    try:
        monkeypatch.setenv("FOOTBALL_STORAGE_BACKEND", "postgres")
        monkeypatch.setenv("FOOTBALL_POSTGRES_DSN", postgres_server)
        monkeypatch.setenv("FOOTBALL_POSTGRES_SCHEMA", schema)
        with PostgresReadOnlyStore(postgres_server, schema) as store:
            original = store.query("SELECT * FROM matches WHERE league=? AND season=?", ["SP1", 2024])
        changed = original.iloc[:1].copy()
        changed.loc[:, "home_goals"] = 4

        class Adapter:
            def fetch(self, league, year):
                return Batch(changed, "test://match", "new-digest")

        monkeypatch.setattr("football_analysis.ingest.QUEUE_PATH", tmp_path / "pending.sqlite3")
        monkeypatch.delenv("FOOTBALL_POSTGRES_DSN")
        assert ingest(Adapter(), years=[2024], leagues=["SP1"])[0]["status"] == "deferred"
        monkeypatch.setenv("FOOTBALL_POSTGRES_DSN", postgres_server)
        result = ingest(Adapter(), years=[2024], leagues=["SP1"])
        assert result[0]["status"] == "success"
        import pandas as pd
        pd.DataFrame([{"club_id": 11, "name": "Arsenal", "domestic_competition_id": "GB1"}]).to_csv(
            tmp_path / "clubs.csv.gz", index=False,
        )
        pd.DataFrame([{"player_id": 7, "image_url": "https://example.test/7.jpg"}]).to_csv(
            tmp_path / "players.csv.gz", index=False,
        )
        pd.DataFrame([{"player_id": 7, "player_name": "Example", "transfer_date": "2026-09-03",
                       "transfer_season": "26/27", "from_club_id": 99, "to_club_id": 11,
                       "from_club_name": "Old", "to_club_name": "Old", "transfer_fee": 100,
                       "market_value_in_eur": 200}]).to_csv(tmp_path / "transfers.csv.gz", index=False)
        assert sync_transfers(directory=tmp_path) == 1
        with PostgresReadOnlyStore(postgres_server, schema) as store:
            assert store.scalar("SELECT count(*) FROM matches WHERE league=? AND season=?", ["SP1", 2024]) == 1
            assert store.scalar("SELECT home_goals FROM matches WHERE league=? AND season=?", ["SP1", 2024]) == 4
            assert store.scalar("SELECT count(*) FROM elo_ratings WHERE league=? AND season=?", ["SP1", 2024]) == 4
            assert store.scalar("SELECT count(*) FROM transfers") == 1
        from football_analysis.api.contracts import RefreshRequest
        from football_analysis.api.refresh import RefreshRunReport
        import time

        app = create_app(tmp_path / "refresh.duckdb", refresh_runner=lambda *_: RefreshRunReport())
        endpoint = next(route.endpoint for route in app.routes if route.path == "/api/v1/refresh" and "POST" in route.methods)
        endpoint(RefreshRequest(target_step=1))
        for _ in range(100):
            if app.state.refresh.status().status != "running":
                break
            time.sleep(0.01)
        assert app.state.refresh.status().status == "success"
        assert isinstance(app.state.store, PostgresReadOnlyStore)
        app.state.store.close()
    finally:
        with _connect(postgres_server, autocommit=True) as conn:
            conn.execute(f"DROP SCHEMA {schema} CASCADE")


def test_sqlite_read_fallback_preserves_api_data(match_db, postgres_server, monkeypatch):
    from football_analysis.api.db import SQLiteReadOnlyStore

    schema = "fallback_test_" + uuid.uuid4().hex
    copy_snapshot(match_db, postgres_server, schema)
    local = match_db.with_suffix(".sqlite3")
    try:
        counts = refresh_local_snapshot(postgres_server, schema, local)
        assert counts["matches"] == 3
        original_size = local.stat().st_size
        with pytest.raises(ValueError, match="verified snapshot"):
            refresh_local_snapshot(postgres_server, "missing_snapshot_schema", local)
        assert local.stat().st_size == original_size
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
        monkeypatch.setattr("football_analysis.api.postgres_matches._connect", unavailable)
        outage_app = create_app(match_db)
        assert isinstance(outage_app.state.store, SQLiteReadOnlyStore)
        outage_app.state.store.close()
    finally:
        with _connect(postgres_server, autocommit=True) as conn:
            conn.execute(f"DROP SCHEMA {schema} CASCADE")


def test_match_read_model_rejects_public_schema(monkeypatch):
    monkeypatch.setenv("FOOTBALL_POSTGRES_SCHEMA", "public")
    with pytest.raises(ValueError, match="private application schema"):
        _schema_name()


def test_postgres_writer_requires_explicit_dsn():
    with pytest.raises(ValueError, match="FOOTBALL_POSTGRES_DSN"):
        PostgresWriteStore("", "football_analysis_next")


def test_json_round_trip_keeps_shared_match_semantics(match_db):
    """Always runs, including on machines without a PostgreSQL service."""
    import pandas as pd

    with ReadOnlyStore(match_db) as store:
        raw = load_match_source_rows(store)
        copy = pd.DataFrame(_encode_rows(raw))
        for kwargs in ({}, {"query": "Barcelna"}, {"query": "fc"}, {"limit": 1}):
            expected = list_matches(store, competition="SP1", season=2024, **kwargs)
            actual = list_matches(store, competition="SP1", season=2024, raw_frame=copy, **kwargs)
            assert actual.model_dump(mode="json") == expected.model_dump(mode="json")


def test_route_switch_and_missing_partition_without_postgres(match_db, monkeypatch):
    """Exercise route selection even when the optional PostgreSQL driver is absent."""
    import json
    import pandas as pd

    with ReadOnlyStore(match_db) as store:
        frame = load_match_source_rows(store)
    frame = pd.DataFrame(_encode_rows(frame[frame.competition == "SP1"]))
    partition = Partition(frame, version=1, row_count=len(frame), checksum="example")
    monkeypatch.setenv("FOOTBALL_MATCH_READ_BACKEND", "postgres")
    monkeypatch.setenv("FOOTBALL_POSTGRES_DSN", "postgresql://unused")
    monkeypatch.setattr("football_analysis.api.app.read_partition", lambda *_: partition)
    app = create_app(match_db)
    route = next(route.endpoint for route in app.routes if getattr(route, "path", None) == "/api/v1/matches")
    kwargs = dict(competition="SP1", season=2024, team=None, opponent=None, venue=None,
                  q="Barcelna", cursor=None, limit=50)
    request = Request({"type": "http", "headers": []})
    response = route(request, **kwargs)
    assert response.status_code == 200
    assert json.loads(response.body)["source"]["source"] == "postgresql"
    assert response.headers["ETag"]

    def missing(*_):
        raise PartitionUnavailable("missing")

    monkeypatch.setattr("football_analysis.api.app.read_partition", missing)
    with pytest.raises(HTTPException, match="missing") as exc:
        route(request, **kwargs)
    assert exc.value.status_code == 503

    monkeypatch.setenv("FOOTBALL_MATCH_READ_BACKEND", "duckdb")
    duck_app = create_app(match_db)
    duck_route = next(route.endpoint for route in duck_app.routes if getattr(route, "path", None) == "/api/v1/matches")
    assert json.loads(duck_route(request, **kwargs).body)["source"]["source"] == "duckdb"
    app.state.store.close()
    duck_app.state.store.close()


def test_partition_parity_dedup_search_order_and_cursors(match_db, pg_dsn, monkeypatch):
    first_publish = publish_partition(match_db, pg_dsn, "SP1", 2024)
    again = publish_partition(match_db, pg_dsn, "SP1", 2024)
    assert first_publish.version == again.version == 1
    assert first_publish.row_count == again.row_count
    assert read_partition(pg_dsn, "SP1", 2024).checksum == first_publish.checksum

    monkeypatch.setenv("FOOTBALL_MATCH_READ_BACKEND", "duckdb")
    duck = TestClient(create_app(match_db))
    monkeypatch.setenv("FOOTBALL_MATCH_READ_BACKEND", "postgres")
    monkeypatch.setenv("FOOTBALL_POSTGRES_DSN", pg_dsn)
    pg = TestClient(create_app(match_db))

    scope = {"competition": "SP1", "season": 2024}
    for extra in ({}, {"q": "Barcelna"}, {"q": "fc"}, {"q": "ar"},
                  {"team": "Barcelona"}, {"team": "Barcelona", "venue": "Home"},
                  {"team": "Barcelona", "opponent": "Real Madrid"}):
        params = {**scope, **extra}
        assert _body(pg.get("/api/v1/matches", params=params)) == _body(duck.get("/api/v1/matches", params=params))

    duck_cursor = pg_cursor = None
    all_matches = []
    while True:
        params = {**scope, "limit": 1}
        if duck_cursor:
            params["cursor"] = duck_cursor
        duck_page = _body(duck.get("/api/v1/matches", params=params))
        params.pop("cursor", None)
        if pg_cursor:
            params["cursor"] = pg_cursor
        pg_page = _body(pg.get("/api/v1/matches", params=params))
        assert pg_page == duck_page
        all_matches.extend(pg_page["matches"])
        duck_cursor = duck_page["page"]["next_cursor"]
        pg_cursor = pg_page["page"]["next_cursor"]
        if not pg_cursor:
            break
    assert len(all_matches) == 4  # completed duplicate and superseded fixture are removed
    assert all_matches[0]["home"]["name"] == "FC Barcelona"  # upcoming first
    assert pg.get("/api/v1/matches", params=scope).json()["source"]["source"] == "postgresql"


def test_partition_integrity_version_and_switch_rollback(match_db, pg_dsn, monkeypatch):
    import psycopg

    initial = publish_partition(match_db, pg_dsn, "SP1", 2024)
    with connect(match_db) as con:
        con.execute("""
            INSERT INTO matches
                (league, season, match_date, home_team, away_team, home_goals, away_goals)
            VALUES ('SP1', 2024, '2024-08-04', 'Valencia', 'Barcelona', 1, 1)
        """)
    changed = publish_partition(match_db, pg_dsn, "SP1", 2024)
    assert changed.version == initial.version + 1
    assert changed.row_count == initial.row_count + 1

    monkeypatch.setenv("FOOTBALL_MATCH_READ_BACKEND", "postgres")
    monkeypatch.setenv("FOOTBALL_POSTGRES_DSN", pg_dsn)
    pg = TestClient(create_app(match_db))
    params = {"competition": "SP1", "season": 2024}
    response = pg.get("/api/v1/matches", params=params)
    assert response.status_code == 200
    assert pg.get("/api/v1/matches", params=params, headers={"If-None-Match": response.headers["ETag"]}).status_code == 304
    assert pg.get("/api/v1/matches", params={"competition": "E0", "season": 2024}).status_code == 503
    with psycopg.connect(pg_dsn) as conn:
        conn.execute("DELETE FROM match_read_rows WHERE competition = %s AND season = %s AND ordinal = 0", ("SP1", 2024))
    assert pg.get("/api/v1/matches", params=params).status_code == 503

    monkeypatch.setenv("FOOTBALL_MATCH_READ_BACKEND", "duckdb")
    duck = TestClient(create_app(match_db))
    assert duck.get("/api/v1/matches", params=params).status_code == 200
    repaired = publish_partition(match_db, pg_dsn, "SP1", 2024)
    assert repaired.version == changed.version + 1
    assert read_partition(pg_dsn, "SP1", 2024).row_count == changed.row_count


def test_private_snapshot_copy_is_verified_and_repeatable(match_db, postgres_server):
    import psycopg

    schema = "snapshot_test_" + uuid.uuid4().hex
    with connect(match_db) as con:
        con.execute("CREATE TABLE transfers (transfer_id VARCHAR, fee DOUBLE)")
        con.execute("INSERT INTO transfers VALUES ('transfer-1', 123.5)")
        con.execute("INSERT INTO elo_ratings VALUES ('SP1', 2024, '2024-08-01', 'Barcelona', 'Real Madrid', 'Home', 1500.0, 1513.176486149602, 13.17648614960195)")
    low_precision_dsn = psycopg.conninfo.make_conninfo(postgres_server, options="-c extra_float_digits=0")
    with _connect(low_precision_dsn) as conn:
        assert int(conn.execute("SHOW extra_float_digits").fetchone()[0]) >= 1
    counts = copy_snapshot(match_db, low_precision_dsn, schema)
    assert counts["matches"] == 3
    assert counts["recent_events"] == 3
    assert counts["transfers"] == 1
    assert copy_snapshot(match_db, low_precision_dsn, schema) == counts
    with psycopg.connect(postgres_server) as conn:
        assert conn.execute(
            "SELECT nspacl FROM pg_namespace WHERE nspname = %s", [schema],
        ).fetchone()[0] == [f"{conn.info.user}=UC/{conn.info.user}"]
        conn.execute(f'UPDATE "{schema}".matches SET home_goals = 99')
    with pytest.raises(ValueError, match="failed verification"):
        copy_snapshot(match_db, low_precision_dsn, schema)


def test_postgres_snapshot_supports_shared_api_queries(match_db, postgres_server):
    from football_analysis.api import queries

    schema = "snapshot_test_" + uuid.uuid4().hex
    copy_snapshot(match_db, postgres_server, schema)
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


def test_postgres_snapshot_api_switch_and_refresh_guard(match_db, postgres_server, monkeypatch):
    import psycopg

    schema = "snapshot_test_" + uuid.uuid4().hex
    with psycopg.connect(postgres_server) as conn:
        conn.execute(f'CREATE SCHEMA "{schema}"')
    with pytest.raises(ValueError, match="no verified snapshot"):
        PostgresReadOnlyStore(postgres_server, schema)
    with psycopg.connect(postgres_server) as conn:
        conn.execute(f'DROP SCHEMA "{schema}"')
    copy_snapshot(match_db, postgres_server, schema)
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
        assert pg.post("/api/v1/refresh", json={"step": 1}).status_code == 409
    finally:
        pg_app.state.store.close()
        duck_app.state.store.close()


@pytest.mark.skipif(not os.environ.get("FOOTBALL_VERIFY_FULL_SNAPSHOT"), reason="large local data check is opt-in")
def test_full_local_snapshot_against_temporary_postgres(postgres_server, monkeypatch):
    from football_analysis.config import DB

    if not DB.exists():
        pytest.skip("No local DuckDB source snapshot")
    schema = "full_snapshot_test_" + uuid.uuid4().hex
    counts = copy_snapshot(DB, postgres_server, schema)
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
