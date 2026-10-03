from datetime import date, datetime, timedelta
from pathlib import Path
import os
import shutil
import tempfile
import time

import pandas as pd
from fastapi.testclient import TestClient

from football_analysis.api.app import create_app
from football_analysis.ingest import connect


WAREHOUSE = Path(__file__).resolve().parents[1] / "warehouse"
_DBT_WORK = Path(tempfile.gettempdir()) / "football-test-dbt"  # fixed so dbt can reuse its parse


def build_marts(path):
    """dbt run of the marts the API reads (tag:serving) against a test database, in-process.

    dbt keeps its DuckDB handle open inside this process, so it works on a copy that is then
    checkpointed and copied back; the caller's file stays free for read-only connections.
    """
    # dbt loads any .env it finds above the working directory (on import and on invoke); restore the
    # environment afterwards so tests never pick up a real FOOTBALL_POSTGRES_DSN.
    saved = dict(os.environ)
    from dbt.cli.main import dbtRunner

    work = Path(tempfile.mkdtemp()) / "dbt.duckdb"
    shutil.copyfile(path, work)
    os.environ["FOOTBALL_DUCKDB"] = str(work)
    try:
        result = dbtRunner().invoke([
            "run", "--project-dir", str(WAREHOUSE), "--profiles-dir", str(WAREHOUSE), "--select", "+tag:serving",
            "--target-path", str(_DBT_WORK / "target"), "--log-path", str(_DBT_WORK / "logs"), "--quiet",
            "--no-send-anonymous-usage-stats",
        ])
    finally:
        os.environ.clear()
        os.environ.update(saved)
    assert result.success, result.exception
    with connect(work) as con:
        con.execute("CHECKPOINT")  # fold dbt's WAL into the file before copying it back
    shutil.copyfile(work, path)


_seeded = None


def seed(path):
    """Seed the raw app tables and build the marts once, then copy that database per test."""
    global _seeded
    if _seeded is None:
        _seeded = Path(tempfile.mkdtemp()) / "seed.duckdb"
        _seed_raw(_seeded)
        build_marts(_seeded)
    shutil.copyfile(_seeded, path)


def _seed_raw(path):
    with connect(path) as con:
        con.execute("""
            INSERT INTO matches (
                league, season, match_date, home_team, away_team, home_goals, away_goals,
                home_shots, away_shots, home_sot, away_sot, half_time_home_goals, half_time_away_goals,
                home_corners, away_corners, home_fouls, away_fouls, home_yellows, away_yellows,
                home_reds, away_reds, referee
            ) VALUES
            ('E0', 2024, '2024-08-17', 'Arsenal', 'Liverpool', 2, 1, 12, 8, 5, 3, 1, 0, 7, 4, 11, 9, 1, 2, 0, 0, 'Example'),
            ('E0', 2024, '2024-08-24', 'Chelsea', 'Arsenal', 0, 1, 9, 11, 2, 4, 0, 1, 3, 6, 10, 8, 2, 1, 0, 0, 'Example')
        """)
        con.execute("""
            INSERT INTO ingestion_runs (run_id, league, season, source_url, sha256, row_count, status, detail)
            VALUES ('r1', 'E0', 2024, 'memory', 'abc123', 2, 'success', 'ok')
        """)
        con.execute("""
            INSERT INTO reference_standings (
                source, league, season, rank, team, played, points, goal_difference,
                form, description, source_updated_at, fetched_at
            ) VALUES ('TheSportsDB', 'E0', 2024, 1, 'Arsenal', 2, 7, 2,
                      'WW', 'Champions League', current_timestamp, current_timestamp)
        """)
        con.execute("""
            INSERT INTO tournament_matches (
                competition, season, stage, group_name, match_date, home_team, away_team,
                home_goals, away_goals, home_penalties, away_penalties, venue, neutral, status,
                source, source_url, fetched_at
            ) VALUES (
                'UCL', 2024, 'Group stage', 'A', '2024-09-18', 'Arsenal', 'Paris SG',
                2, 0, NULL, NULL, 'London', TRUE, 'FT', 'openfootball', 'memory', current_timestamp
            )
        """)
        con.execute("""
            INSERT INTO tournament_goals (
                competition, season, match_date, team, player, minute, penalty, own_goal,
                source, source_url, fetched_at
            ) VALUES (
                'UCL', 2024, '2024-09-18', 'Arsenal', 'Bukayo Saka', '12', FALSE, FALSE,
                'openfootball', 'memory', current_timestamp
            )
        """)
        con.execute("""
            INSERT INTO open_players (
                source, player_id, team_id, team, player, position, sub_position, nationality,
                date_born, foot, height_cm, market_value_eur, highest_market_value_eur, image_url,
                profile_url, last_season, data_as_of, fetched_at
            ) VALUES (
                'transfermarkt', 'p-saka', 'arsenal', 'Arsenal', 'Bukayo Saka', 'Attack',
                'Right Winger', 'England', '2001-09-05', 'left', 178, 140000000, 140000000,
                NULL, NULL, 2025, '2026-01-01', current_timestamp
            )
        """)
        con.execute("""
            INSERT INTO open_player_stats (
                source, player_id, team, season, competition_id, competition, competition_type,
                appearances, goals, assists, minutes_played, yellow_cards, red_cards, data_as_of, fetched_at
            ) VALUES (
                'transfermarkt', 'p-saka', 'Arsenal', 2024, 'GB1', 'premier-league', 'domestic_league',
                36, 16, 10, 3100, 4, 0, '2026-01-01', current_timestamp
            )
        """)
        con.execute("""
            INSERT INTO prediction_models (
                model_id, model_name, trained_at, validation_cutoff, train_matches, validation_matches,
                feature_names, parameters, metrics
            ) VALUES (
                'softmax-test', 'Regularized softmax', current_timestamp, '2025-03-01', 100, 20,
                '[]', '{}', '{"accuracy": 0.5, "log_loss": 1.0, "baseline_accuracy": 0.43}'
            )
        """)
        con.execute("""
            INSERT INTO match_predictions (
                model_id, prediction_kind, league, season, match_date, home_team, away_team,
                actual_result, predicted_result, home_probability, draw_probability, away_probability
            ) VALUES
            ('softmax-test', 'forecast', 'E0', 2026, '2026-09-20', 'Arsenal', 'Chelsea',
             NULL, 'Home', 0.52, 0.27, 0.21),
            ('softmax-test', 'validation', 'E0', 2024, '2024-08-17', 'Arsenal', 'Liverpool',
             'Home', 'Home', 0.48, 0.30, 0.22)
        """)
        con.execute("""
            INSERT INTO analytics_metadata (cache_key, refreshed_at, match_rows)
            VALUES ('elo', current_timestamp, 2)
        """)
        con.execute("""
            INSERT INTO shot_efficiency_cache (
                league, season, team, matches, coverage_pct, shots_per_match,
                shot_accuracy_pct, goals_per_shot_pct, goals_per_sot_pct
            ) VALUES ('E0', 2024, 'Arsenal', 2, 100, 11.5, 39.1, 13.0, 33.3)
        """)
        con.execute("""
            INSERT INTO recent_events (
                event_id, league, season, match_date, home_team, away_team,
                home_goals, away_goals, status, event_kind, source, fetched_at
            ) VALUES ('event-1', 'E0', 2024, '2024-08-17', 'Arsenal', 'Liverpool',
                      2, 1, 'Match Finished', 'past', 'TheSportsDB', current_timestamp)
        """)
        con.execute("""
            INSERT INTO recent_events (
                event_id, league, season, match_date, home_team, away_team,
                home_goals, away_goals, status, event_kind, source, fetched_at
            ) VALUES ('event-next', 'E0', 2026, ?, 'Arsenal', 'Chelsea',
                      NULL, NULL, 'Not Started', 'next', 'TheSportsDB', current_timestamp)
        """, [date.today() + timedelta(days=2)])
        con.execute("""
            INSERT INTO event_statistics (source, event_id, statistic, home_value, away_value, fetched_at)
            VALUES
                ('TheSportsDB', 'event-1', 'Shots on Goal', 5, 3, current_timestamp),
                ('TheSportsDB', 'event-1', 'Blocked Shots', 4, 3, current_timestamp)
        """)
        con.execute("""
            INSERT INTO event_timeline (
                source, timeline_id, event_id, minute, event_type, detail, team,
                player_id, player, assist, is_home, comment, fetched_at
            ) VALUES ('TheSportsDB', 'timeline-1', 'event-1', '12', 'Goal', 'Open Play',
                      'Arsenal', 'p-saka', 'Bukayo Saka', '', TRUE, '', current_timestamp)
        """)
        con.execute("""
            INSERT INTO event_lineups (
                source, lineup_id, event_id, team, player_id, player, position,
                is_home, is_substitute, shirt_number, cutout_url, fetched_at
            ) VALUES ('TheSportsDB', 'lineup-1', 'event-1', 'Arsenal', 'p-saka',
                      'Bukayo Saka', 'Right Wing', TRUE, FALSE, '7', NULL, current_timestamp)
        """)
        con.execute("""
            INSERT INTO match_contexts (
                source, match_id, competition_id, season, match_date, home_team, away_team,
                home_coach, away_coach, home_formation, away_formation, stadium,
                attendance, referee, source_url, fetched_at
            ) VALUES (
                'Transfermarkt Open Dataset', 'game-1', 'GB1', 2024, '2024-08-17',
                'Arsenal FC', 'Liverpool FC', 'Mikel Arteta', 'Arne Slot', '4-3-3',
                '4-2-3-1', 'Emirates Stadium', 60200, 'Example', 'memory', current_timestamp
            )
        """)
        con.execute("""
            CREATE TABLE IF NOT EXISTS transfers (
                transfer_id VARCHAR,
                player_id VARCHAR,
                player_name VARCHAR,
                transfer_date DATE,
                transfer_season VARCHAR,
                season INTEGER,
                from_club_id VARCHAR,
                from_club_name VARCHAR,
                to_club_id VARCHAR,
                to_club_name VARCHAR,
                transfer_fee DOUBLE,
                market_value_eur BIGINT,
                from_competition VARCHAR,
                to_competition VARCHAR,
                image_url VARCHAR
            );
        """)
        con.execute("""
            INSERT INTO transfers VALUES (
                't1', 'p-rice', 'Declan Rice', '2023-07-15', '23/24', 2023,
                '379', 'West Ham United', '11', 'Arsenal', 116600000, 110000000,
                'E0', 'E0', 'https://img.example/rice.jpg'
            );
        """)


def client(tmp_path):
    db = tmp_path / "api.duckdb"
    seed(db)
    return TestClient(create_app(db))


def test_health_and_openapi_document_v1_routes(tmp_path):
    api = client(tmp_path)
    health = api.get("/api/v1/health")
    assert health.status_code == 200
    assert health.json()["status"] == "ok"
    spec = api.get("/openapi.json").json()
    for path in (
        "/api/v1/catalog", "/api/v1/teams", "/api/v1/matches", "/api/v1/analysis",
        "/api/v1/tournaments/{competition}/{season}", "/api/v1/predictions",
        "/api/v1/players", "/api/v1/players/{player_id}", "/api/v1/quality",
        "/api/v1/overview", "/api/v1/transfers",
        "/api/v1/standings",
        "/api/v1/shots", "/api/v1/event-details", "/api/v1/event-details/{event_id}",
        "/api/v1/match-detail", "/api/v1/refresh",
    ):
        assert path in spec["paths"]
    assert spec["info"]["version"] == "1.0.0"


def test_catalog_teams_and_analysis_contract(tmp_path):
    api = client(tmp_path)
    catalog = api.get("/api/v1/catalog")
    assert catalog.status_code == 200
    assert "ETag" in catalog.headers
    assert "max-age" in catalog.headers["Cache-Control"]
    codes = {item["code"] for item in catalog.json()["competitions"]}
    assert {"E0", "UCL"} <= codes
    teams = api.get("/api/v1/teams", params={"competition": "E0", "season": 2024}).json()["teams"]
    ids = {team["team_id"] for team in teams}
    assert "arsenal" in ids
    names = {team["name"] for team in teams}
    assert "Arsenal" in names
    historical = api.get("/api/v1/teams", params={"competition": "E0", "season": 2024})
    assert "max-age=86400" in historical.headers["Cache-Control"]
    report = api.post("/api/v1/analysis", json={
        "competitions": ["E0"], "seasons": [2024], "teams": ["arsenal"], "form_window": 5,
    }).json()
    assert report["match_count"] == 2
    assert report["filters"]["teams"] == ["arsenal"]
    assert report["rankings"][0]["team"]["team_id"] == "arsenal"
    assert "points_per_game" in report["correlations"][0]
    assert report["match_factors"]["corners_mean"] is not None


def test_matches_use_cursor_pagination_and_etags(tmp_path):
    api = client(tmp_path)
    first = api.get("/api/v1/matches", params={"limit": 1})
    assert first.status_code == 200
    payload = first.json()
    assert payload["page"]["returned"] == 1
    assert payload["page"]["next_cursor"]
    second = api.get("/api/v1/matches", params={"limit": 1, "cursor": payload["page"]["next_cursor"]})
    assert second.json()["matches"][0]["match_date"] != payload["matches"][0]["match_date"]
    h2h = api.get("/api/v1/matches", params={"team": "Arsenal", "opponent": "Liverpool", "limit": 200})
    assert len(h2h.json()["matches"]) == 1
    etag = first.headers["ETag"]
    cached = api.get("/api/v1/matches", params={"limit": 1}, headers={"If-None-Match": etag})
    assert cached.status_code == 304


def test_match_search_handles_short_alias_and_no_results(tmp_path):
    db = tmp_path / "spain-search.duckdb"
    seed(db)
    with connect(db) as con:
        con.execute(
            "INSERT INTO recent_matches (league, season, match_date, home_team, away_team, "
            "home_goals, away_goals, source, fetched_at) VALUES "
            "('SP1', 2026, '2026-09-20', 'Barcelona', 'Real Madrid', 2, 1, 'test', current_timestamp)"
        )
    api = TestClient(create_app(db))
    found = api.get("/api/v1/matches", params={"competition": "SP1", "season": 2026, "q": "fc", "limit": 20})
    assert found.status_code == 200
    assert [match["home"]["name"] for match in found.json()["matches"]] == ["FC Barcelona"]
    typo = api.get("/api/v1/matches", params={"competition": "SP1", "season": 2026, "q": "Barcelna"})
    assert [match["home"]["name"] for match in typo.json()["matches"]] == ["FC Barcelona"]
    short_fragment = api.get("/api/v1/matches", params={"competition": "SP1", "season": 2026, "q": "ar"})
    assert short_fragment.json()["matches"] == []
    missing = api.get("/api/v1/matches", params={"competition": "SP1", "season": 2026, "q": "no-such-club", "limit": 20})
    assert missing.status_code == 200
    assert missing.json()["matches"] == []
    assert missing.json()["page"]["next_cursor"] is None


def test_tournament_players_predictions_and_quality(tmp_path):
    api = client(tmp_path)
    tourney = api.get("/api/v1/tournaments/UCL/2024").json()
    assert tourney["stages"][0]["stage"] == "Group stage"
    assert tourney["scorers"][0]["player"] == "Bukayo Saka"
    players = api.get("/api/v1/players", params={"q": "Saka"}).json()
    assert players["players"][0]["player_id"] == "p-saka"
    profile = api.get("/api/v1/players/p-saka").json()
    assert profile["stats"][0]["goals"] == 16
    missing = api.get("/api/v1/players/missing")
    assert missing.status_code == 404
    preds = api.get("/api/v1/predictions").json()
    assert preds["metrics"]["accuracy"] == 0.5
    assert preds["forecasts"][0]["home"]["team_id"] == "arsenal"
    assert preds["calibration"][0]["samples"] == 1
    quality = api.get("/api/v1/quality").json()
    assert quality["match_records"] >= 2
    assert quality["reference_rows"] == 1
    assert quality["tracked_players"] == 1
    assert quality["tournament_matches"] == 1
    assert quality["detailed_event_stats"] == 2
    assert quality["shot_coverage"]
    assert quality["source_caps"]
    assert len(quality["fixture_coverage"]) == 10


def test_missing_database_is_unavailable(tmp_path):
    api = TestClient(create_app(tmp_path / "absent.duckdb"))
    assert api.get("/api/v1/health").json()["status"] == "unavailable"
    assert api.get("/api/v1/catalog").status_code == 503


def test_cors_preflight_and_origin_headers(tmp_path):
    api = client(tmp_path)
    for origin in ("http://localhost:3000", "http://localhost:3001", "http://127.0.0.1:3001"):
        preflight = api.options(
            "/api/v1/catalog",
            headers={
                "Origin": origin,
                "Access-Control-Request-Method": "GET",
            },
        )
        assert preflight.status_code == 200
        assert preflight.headers.get("access-control-allow-origin") == origin

        get_res = api.get("/api/v1/catalog", headers={"Origin": origin})
        assert get_res.status_code == 200
        assert get_res.headers.get("access-control-allow-origin") == origin


def test_overview_endpoint(tmp_path):
    api = client(tmp_path)
    res = api.get("/api/v1/overview", params={"team": "Arsenal", "competition": "E0", "season": 2024})
    assert res.status_code == 200
    data = res.json()
    assert "spotlight" in data
    assert data["spotlight"]["team"]["name"] == "Arsenal"
    assert "performance_over_time" in data
    assert "forecasts" in data

    live = api.get("/api/v1/overview", params={"team": "Arsenal", "competition": "E0", "season": 2026}).json()
    assert live["spotlight"]["next_match"]["away"]["name"] == "Chelsea"


def test_standings_include_external_reference_deltas(tmp_path):
    api = client(tmp_path)
    data = api.get("/api/v1/standings", params={"competition": "E0", "season": 2024}).json()
    assert data["rankings"][0]["team"]["name"] == "Arsenal"
    assert data["reference"][0]["results_points"] == 6
    assert data["reference"][0]["point_adjustment"] == 1


def test_player_search_and_facets_cover_legacy_filters(tmp_path):
    api = client(tmp_path)
    by_nation = api.get("/api/v1/players", params={"q": "England"}).json()
    assert by_nation["players"][0]["name"] == "Bukayo Saka"
    assert by_nation["total_count"] == 1
    assert by_nation["nationality_count"] == 1
    assert by_nation["teams"][0]["name"] == "Arsenal"
    by_position = api.get("/api/v1/players", params={"position": "Attack"}).json()
    assert by_position["players"][0]["position"] == "Attack"
    typo = api.get("/api/v1/players", params={"q": "Skaa"}).json()
    assert typo["players"][0]["name"] == "Bukayo Saka"
    short_fragment = api.get("/api/v1/players", params={"q": "ka"}).json()
    assert short_fragment["players"] == []


def test_transfers_with_all_filter(tmp_path):
    api = client(tmp_path)
    res = api.get("/api/v1/transfers", params={"competition": "all", "season": "all"})
    assert res.status_code == 200
    data = res.json()
    assert "transfers" in data
    assert len(data["transfers"]) >= 1


def test_shots_and_event_details_contract(tmp_path):
    api = client(tmp_path)
    shots = api.get("/api/v1/shots", params={"competition": "E0", "season": 2024})
    assert shots.status_code == 200
    assert shots.json()["teams"][0]["team"]["team_id"] == "arsenal"
    assert shots.json()["coverage"][0]["coverage_pct"] == 100

    events = api.get("/api/v1/event-details", params={"competition": "E0"})
    assert events.status_code == 200
    assert events.json()["events"][0]["statistics_count"] == 2
    detail = api.get("/api/v1/event-details/event-1")
    assert detail.status_code == 200
    assert any(row["statistic"] == "Shots on Goal" for row in detail.json()["statistics"])
    assert detail.json()["timeline"][0]["player"] == "Bukayo Saka"
    assert detail.json()["lineups"][0]["shirt_number"] == "7"
    assert api.get("/api/v1/event-details/missing").status_code == 404


def test_match_centre_combines_stored_stats_context_and_events(tmp_path):
    api = client(tmp_path)
    detail = api.get("/api/v1/match-detail", params={
        "competition": "E0", "season": 2024, "match_date": "2024-08-17",
        "home": "Arsenal", "away": "Liverpool",
    })
    assert detail.status_code == 200
    payload = detail.json()
    assert payload["home_coach"] == "Mikel Arteta"
    assert payload["away_formation"] == "4-2-3-1"
    assert payload["stadium"] == "Emirates Stadium"
    assert {row["statistic"] for row in payload["statistics"]} >= {"Corners", "Fouls"}
    assert payload["timeline"][0]["player"] == "Bukayo Saka"
    assert any("12 to 8" in sentence for sentence in payload["narrative"])
    assert all("4 to 3" not in sentence for sentence in payload["narrative"])
    assert any("2 goals." in sentence for sentence in payload["narrative"])
    assert payload["lineup_complete"] is False


def test_refresh_workflow_reports_step_progress_and_reopens_database(tmp_path):
    db = tmp_path / "api.duckdb"
    seed(db)

    def fake_runner(request, progress):
        progress(1, "Results and fixtures", "Testing")
        progress(2, "Tables and competitions", "Testing")

    api = TestClient(create_app(db, refresh_runner=fake_runner))
    started = api.post("/api/v1/refresh", json={"target_step": 2, "season": 2026})
    assert started.status_code == 202
    for _ in range(100):
        status = api.get("/api/v1/refresh").json()
        if status["status"] != "running":
            break
        time.sleep(0.01)
    assert status["status"] == "success"
    assert status["completed_steps"] == [1, 2]
    assert api.get("/api/v1/health").json()["status"] == "ok"


def test_teams_endpoint_fallback(tmp_path):
    api = client(tmp_path)
    # Season 2026 for E0 when only 2024 matches seeded
    res = api.get("/api/v1/teams", params={"competition": "E0", "season": 2026})
    assert res.status_code == 200
    data = res.json()
    assert "teams" in data
    assert len(data["teams"]) >= 2
