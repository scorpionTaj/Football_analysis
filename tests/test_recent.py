import football_analysis.recent as recent
import pandas as pd


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
