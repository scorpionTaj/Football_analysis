from football_analysis import pipeline
from football_analysis.api.contracts import RefreshRequest
from football_analysis.api.refresh import RefreshRunReport, _featured_clubs_in_scope, run_refresh_pipeline
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


def test_mixed_results_are_required_failures_and_optional_sources_continue(monkeypatch, tmp_path):
    from football_analysis import fixtures, open_fixtures, recent

    monkeypatch.setattr(recent, "sync_recent", lambda **_kwargs: [
        {"source": "Football-Data.co.uk", "league": "E0", "status": "success"},
        {"source": "Football-Data.co.uk", "league": "D1", "status": "failed", "detail": "CSV down"},
        {"source": "TheSportsDB", "league": "E0", "event_kind": "past", "status": "failed", "detail": "API down"},
    ])
    monkeypatch.setattr(open_fixtures, "sync_open_fixtures", lambda **_kwargs: [
        {"league": "E0", "status": "cached"},
        {"league": "D1", "status": "unavailable", "detail": "schedule down"},
    ])
    monkeypatch.setattr(fixtures, "sync_fixtures", lambda **_kwargs: {"status": "cached"})

    updates = []
    report = run_refresh_pipeline(
        tmp_path / "unused.duckdb", RefreshRequest(target_step=1, season=2026, competitions=["E0", "D1"]),
        lambda *args: updates.append(args),
    )
    assert len(report.required_failures) == 1
    assert len(report.failures) == 3
    assert {row.source for row in report.failures} == {"Football-Data.co.uk", "TheSportsDB", "OpenFootball fixtures"}
    assert updates[-1][1] == "Results and fixtures"


def test_optional_outage_keeps_football_sync_exit_zero(monkeypatch, tmp_path, capsys):
    import json
    import sys

    report = RefreshRunReport()
    report.add(1, "Football-Data.co.uk", {"league": "E0", "status": "cached"}, required=True)
    report.add(2, "Reference standings", {"league": "E0", "status": "failed", "detail": "offline"})
    monkeypatch.setattr(pipeline, "run_refresh_pipeline", lambda *_args: report)
    monkeypatch.setattr(sys, "argv", ["football-sync", "--step", "2"])
    pipeline.main()
    summary = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert summary["status"] == "degraded"
    assert summary["failed_count"] == 0
    assert summary["degraded_count"] == 1


def test_required_result_failure_makes_football_sync_exit_nonzero(monkeypatch, tmp_path, capsys):
    import json
    import sys
    import pytest

    report = RefreshRunReport()
    report.add(1, "Football-Data.co.uk", {"league": "E0", "status": "failed", "detail": "CSV down"}, required=True)
    monkeypatch.setattr(pipeline, "run_refresh_pipeline", lambda *_args: report)
    monkeypatch.setattr(sys, "argv", ["football-sync", "--step", "1"])
    with pytest.raises(SystemExit) as exc:
        pipeline.main()
    assert exc.value.code == 1
    assert json.loads(capsys.readouterr().out.strip().splitlines()[-1])["status"] == "failed"


def test_all_four_stages_keep_running_after_optional_source_failures(monkeypatch, tmp_path):
    import pandas as pd
    from football_analysis import event_details, fixtures, history, ingest, media, open_fixtures, open_players, recent, reference_standings, transfers, warehouse
    from football_analysis.api import refresh
    from football_analysis.ml import train

    monkeypatch.setattr(recent, "sync_recent", lambda **_kwargs: [
        {"source": "Football-Data.co.uk", "league": "E0", "status": "success"},
    ])
    monkeypatch.setattr(open_fixtures, "sync_open_fixtures", lambda **_kwargs: [])
    monkeypatch.setattr(fixtures, "sync_fixtures", lambda **_kwargs: {"status": "cached"})
    monkeypatch.setattr(reference_standings, "sync", lambda **_kwargs: [
        {"league": "E0", "status": "failed", "detail": "standings offline"},
    ])
    monkeypatch.setattr(open_players, "sync_open_players", lambda **_kwargs: (_ for _ in ()).throw(RuntimeError("snapshot offline")))
    monkeypatch.setattr(transfers, "sync_transfers", lambda **_kwargs: 0)
    monkeypatch.setattr(refresh, "_featured_clubs_in_scope", lambda *_args: [])
    monkeypatch.setattr(media, "sync_media", lambda **_kwargs: [])
    monkeypatch.setattr(event_details, "sync_event_details", lambda **_kwargs: [])
    monkeypatch.setattr(ingest, "refresh_analytics_cache", lambda **_kwargs: None)
    monkeypatch.setattr(history, "fetch_history", lambda **_kwargs: [])
    monkeypatch.setattr(warehouse, "build", lambda **_kwargs: {"status": "success"})
    monkeypatch.setattr(train, "forecast", lambda **_kwargs: pd.DataFrame([{"model": "ensemble", "is_champion": True}]))

    progress = []
    report = run_refresh_pipeline(
        tmp_path / "unused.duckdb", RefreshRequest(target_step=4, season=2026, competitions=["E0"]),
        lambda step, *_args: progress.append(step),
    )
    assert progress == [1, 1, 2, 3, 4]
    assert {row.step for row in report.outcomes} == {1, 2, 3, 4}
    assert len(report.required_failures) == 0
    assert {row.source for row in report.failures} == {"Reference standings", "Open players"}
    assert any(row.source == "Model leaderboard" and row.status == "success" for row in report.outcomes)
