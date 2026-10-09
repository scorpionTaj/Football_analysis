import football_analysis.recent as recent
import pandas as pd
from types import SimpleNamespace

from football_analysis.ingest import connect
from football_analysis.sync_state import mark_fresh


class _Response:
    def raise_for_status(self):
        return None

    def json(self):
        return {"events": [{
            "idEvent": "match-42",
            "strSeason": "2026-2027",
            "dateEvent": "2026-09-15",
            "strTime": "19:45:00",
            "strHomeTeam": "Arsenal",
            "strAwayTeam": "Liverpool",
            "intHomeScore": "2",
            "intAwayScore": "1",
            "strStatus": "Match Finished",
            "strVenue": "Emirates Stadium",
            "strHomeTeamManager": "Mikel Arteta",
            "strAwayManager": "Arne Slot",
            "strHomeFormation": "4-3-3",
            "strAwayFormation": "4-2-3-1",
            "strReferee": "Example Referee",
            "intSpectators": "60200",
        }]}


def test_recent_event_adapter_preserves_available_match_metadata(monkeypatch):
    adapter = recent.TheSportsDBRecentEvents()
    monkeypatch.setattr(adapter.session, "get", lambda *args, **kwargs: _Response())
    monkeypatch.setattr(recent.time, "sleep", lambda _seconds: None)

    frame = adapter.fetch("E0", "past")

    assert list(frame.columns) == recent.EVENT_COLUMNS
    row = frame.iloc[0]
    assert row.home_coach == "Mikel Arteta"
    assert row.away_coach == "Arne Slot"
    assert row.home_formation == "4-3-3"
    assert row.venue == "Emirates Stadium"
    assert row.attendance == 60200


def test_empty_cup_window_is_cached_without_repeated_requests(tmp_path):
    class Adapter:
        calls = 0

        def fetch_season(self, competition, season):
            self.calls += 1
            return pd.DataFrame()

    adapter = Adapter()
    db = tmp_path / "cups.duckdb"
    assert recent.sync_cup_events(
        db=db, season=2026, competitions=["FAC"], adapter=adapter,
    )[0]["status"] == "unavailable"
    assert recent.sync_cup_events(
        db=db, season=2026, competitions=["FAC"], adapter=adapter,
    )[0]["status"] == "cached"
    assert adapter.calls == 1


def test_recent_reports_optional_event_failures_with_cached_results(monkeypatch, tmp_path):
    db = tmp_path / "recent.duckdb"
    with connect(db) as con:
        mark_fresh(con, "recent-matches:E0:2026", "digest")
    monkeypatch.setattr(recent.FootballDataCSV, "fetch", lambda *_args: SimpleNamespace(
        frame=pd.DataFrame(), digest="digest",
    ))

    class FailingEvents:
        def fetch(self, _league, _kind):
            raise RuntimeError("events offline")

    report = recent.sync_recent(db=db, year=2026, leagues=["E0"], event_adapter=FailingEvents())
    assert report[0]["status"] == "cached"
    assert report[0]["source"] == recent.SOURCE_CSV
    assert [row["event_kind"] for row in report[1:]] == ["past", "next"]
    assert all(row["source"] == recent.SOURCE_EVENTS and row["status"] == "failed" for row in report[1:])


def test_new_season_csv_missing_before_kickoff_is_pending_not_failed():
    from datetime import date

    import requests

    from football_analysis.recent import _season_not_started

    missing = requests.HTTPError(response=type("R", (), {"status_code": 404})())
    empty = ValueError("No completed matches are available for this season")
    assert _season_not_started(missing, date(2026, 7, 5)) and _season_not_started(empty, date(2026, 8, 10))
    assert not _season_not_started(missing, date(2026, 11, 1))  # mid-season a missing file is a real failure
    assert not _season_not_started(ValueError("Unexpected league in source"), date(2026, 7, 5))
