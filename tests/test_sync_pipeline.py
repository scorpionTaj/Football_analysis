from football_analysis import pipeline
from football_analysis.api.refresh import _featured_clubs_in_scope
from football_analysis.ingest import connect


def test_incremental_command_reuses_frontend_refresh_stages(monkeypatch, tmp_path):
    seen = {}

    def runner(db, request, progress):
        seen["db"] = db
        seen["request"] = request
        progress(1, "Results and fixtures", "Checking cached sources")

    monkeypatch.setattr(pipeline, "run_refresh_pipeline", runner)
    db = tmp_path / "pipeline.duckdb"
    pipeline.run_pipeline(step=2, competitions=["E0"], season=2026, db=db)
    assert seen["db"] == db
    assert seen["request"].target_step == 2
    assert seen["request"].competitions == ["E0"]
    assert seen["request"].force_download is False


def test_selected_league_only_enriches_its_featured_clubs(tmp_path):
    db = tmp_path / "scope.duckdb"
    with connect(db) as con:
        con.execute("""
            INSERT INTO recent_matches
                (league, season, match_date, home_team, away_team,
                 home_goals, away_goals, source, fetched_at)
            VALUES ('E0', 2026, '2026-09-01', 'Arsenal', 'Man City',
                    2, 1, 'test', current_timestamp)
        """)
    assert _featured_clubs_in_scope(db, {"E0"}, 2026) == ["Manchester City", "Arsenal"]
