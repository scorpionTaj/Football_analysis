from types import SimpleNamespace

from football_analysis.api_football import TEAM_IDS, sync_squads
from football_analysis.ingest import connect


class FakeSession:
    """Answers /status and /players/squads like API-Football, counting the quota down."""

    def __init__(self, remaining):
        self.remaining, self.calls = remaining, []

    def get(self, url, params=None, timeout=None):
        path = url.rsplit("/", 1)[-1] if "squads" not in url else "players/squads"
        self.calls.append(path)
        if path == "status":
            body = {"errors": [], "response": {"requests": {"current": 100 - self.remaining, "limit_day": 100}}}
            headers = {}
        else:
            self.remaining -= 1
            body = {"errors": [], "response": [{"team": {"id": params["team"], "name": "Provider name"}, "players": [
                {"id": 1, "name": "A Player", "age": 24, "number": 7, "position": "Attacker", "photo": "https://x/1.png"},
                {"id": 2, "name": "B Keeper", "age": 30, "number": 1, "position": "Goalkeeper", "photo": None},
            ]}]}
            headers = {"x-ratelimit-requests-remaining": str(self.remaining)}
        return SimpleNamespace(json=lambda: body, headers=headers, url=f"{url}?team={(params or {}).get('team')}",
                               raise_for_status=lambda: None)


def test_without_a_key_nothing_is_called(tmp_path, monkeypatch):
    monkeypatch.delenv("API_FOOTBALL_KEY", raising=False)
    session = FakeSession(100)
    assert sync_squads(db=tmp_path / "x.duckdb", session=session)["status"] == "skipped"
    assert session.calls == []


def test_squads_are_cached_daily_with_provenance_and_stop_at_the_reserve(tmp_path):
    db, clubs = tmp_path / "squads.duckdb", list(TEAM_IDS)[:4]
    session = FakeSession(remaining=22)
    report = sync_squads(db=db, clubs=clubs, key="test", reserve=20, session=session, pause=0)
    assert report["status"] == "partial" and [row["club"] for row in report["updated"]] == clubs[:2]
    assert report["skipped_for_quota"] == clubs[2:] and report["remaining_today"] == 20
    with connect(db) as con:
        rows = con.execute("SELECT team, provider_team, player, source, source_url FROM api_football_squads "
                           "ORDER BY team, player").fetchall()
    assert len(rows) == 4 and rows[0][3] == "API-Football" and rows[0][4].endswith(f"team={TEAM_IDS[rows[0][0]]}")
    # Next run (same day): updated clubs are fresh; only the remaining ones are requested.
    session = FakeSession(remaining=100)
    report = sync_squads(db=db, clubs=clubs, key="test", reserve=20, session=session, pause=0)
    assert report["cached"] == 2 and session.calls == ["status", "players/squads", "players/squads"]
    session = FakeSession(remaining=100)
    assert sync_squads(db=db, clubs=clubs, key="test", session=session, pause=0)["status"] == "cached"
    assert session.calls == []  # fully cached: not even /status
