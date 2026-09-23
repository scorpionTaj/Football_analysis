import json
from datetime import date, timedelta

import pytest

from football_analysis.ingest import connect
from football_analysis.open_fixtures import (
    ALIASES, SOURCE, normalize_open_schedule, sync_open_fixtures,
)
from football_analysis.teams import team_key


def schedule(teams=None):
    teams = teams or [f"Team {index}" for index in range(20)]
    games = []
    for home_index, home in enumerate(teams):
        for away_index, away in enumerate(teams):
            if home == away:
                continue
            round_number = (home_index * 20 + away_index) % 38
            games.append({
                "date": str(date(2026, 8, 1) + timedelta(days=round_number * 7)),
                "team1": home, "team2": away,
                "time": "19:45" if home_index == 0 else None,
            })
    return json.dumps({"name": "Test season", "matches": games}).encode()


class StaticAdapter:
    def __init__(self, raw):
        self.raw = raw

    def fetch(self, league, season):
        assert (league, season) == ("E0", 2026)
        return self.raw


def test_full_schedule_validation_rejects_incomplete_or_implausible_snapshots():
    raw = schedule()
    assert len(normalize_open_schedule(raw, "E0", 2026)) == 380
    document = json.loads(raw)
    document["matches"].pop()
    with pytest.raises(ValueError, match="Expected 380"):
        normalize_open_schedule(json.dumps(document).encode(), "E0", 2026)
    document = json.loads(raw)
    for match in document["matches"]:
        match["date"] = "2026-09-25"
    with pytest.raises(ValueError, match="plausible season"):
        normalize_open_schedule(json.dumps(document).encode(), "E0", 2026)


def test_source_aliases_reconcile_all_checked_2026_league_names():
    assert team_key(ALIASES["Brighton & Hove Albion FC"]) == team_key("Brighton")
    assert team_key(ALIASES["Club Atlético de Madrid"]) == team_key("Ath Madrid")
    assert team_key(ALIASES["Sporting Clube de Portugal"]) == team_key("Sp Lisbon")


def test_full_schedule_import_is_atomic_and_searchable(tmp_path):
    db = tmp_path / "full-fixtures.duckdb"
    today = date(2026, 9, 23)
    teams = [f"Team {index}" for index in range(20)]
    with connect(db) as con:
        for index in range(0, 20, 2):
            con.execute(
                "INSERT INTO recent_matches (league, season, match_date, home_team, away_team, "
                "home_goals, away_goals, source, fetched_at) VALUES "
                "('E0', 2026, '2026-09-20', ?, ?, 1, 0, 'test', current_timestamp)",
                [teams[index], teams[index + 1]],
            )
    full = schedule(teams)
    expected = len(normalize_open_schedule(full, "E0", 2026).query("match_date >= @today"))
    report = sync_open_fixtures(
        db, season=2026, leagues=["E0"], adapter=StaticAdapter(full), today=today,
    )
    assert report == [{"league": "E0", "status": "success", "rows": expected}]
    with connect(db) as con:
        assert con.execute("SELECT count(*) FROM recent_events WHERE source=?", [SOURCE]).fetchone()[0] == expected
    bad = json.dumps({"matches": []}).encode()
    report = sync_open_fixtures(
        db, season=2026, leagues=["E0"], refresh=True,
        adapter=StaticAdapter(bad), today=today,
    )
    assert report[0]["status"] == "unavailable"
    with connect(db) as con:
        assert con.execute("SELECT count(*) FROM recent_events WHERE source=?", [SOURCE]).fetchone()[0] == expected
