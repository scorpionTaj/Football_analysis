import football_analysis.recent as recent


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
