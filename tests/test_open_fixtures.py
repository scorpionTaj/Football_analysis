import json
from datetime import date, timedelta

import pytest

from football_analysis.ingest import connect
from football_analysis.open_fixtures import (
    ALIASES, PROVISIONAL_SOURCE, SOURCE, normalize_open_schedule, sync_open_fixtures,
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
    assert report == [{"league": "E0", "status": "success", "rows": expected, "provisional_results": 0}]
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


def test_scored_matches_become_provisional_results_until_football_data_has_them(tmp_path):
    db = tmp_path / "provisional.duckdb"
    today = date(2026, 9, 23)
    teams = [f"Team {index}" for index in range(20)]
    document = json.loads(schedule(teams))
    played = [m for m in document["matches"] if m["date"] < str(today)]
    for match in played:
        match["score"] = {"ft": [2, 1]}
    with connect(db) as con:  # Football-Data already published the first played match
        for rank, team in enumerate(teams, 1):  # every club is already known, as in real data
            con.execute("INSERT INTO reference_standings (source, league, season, rank, team) VALUES ('t', 'E0', 2026, ?, ?)",
                        [rank, team])
        con.execute(
            "INSERT INTO recent_matches (league, season, match_date, home_team, away_team, "
            "home_goals, away_goals, source, fetched_at) VALUES ('E0', 2026, ?, ?, ?, 3, 3, "
            "'Football-Data.co.uk', current_timestamp)",
            [played[0]["date"], played[0]["team1"], played[0]["team2"]],
        )
    report = sync_open_fixtures(db, season=2026, leagues=["E0"],
                                adapter=StaticAdapter(json.dumps(document).encode()), today=today)
    assert report[0]["provisional_results"] == len(played) - 1
    with connect(db) as con:
        rows = con.execute("SELECT source, home_goals, away_goals FROM recent_matches WHERE home_team=? AND away_team=?",
                           [played[0]["team1"], played[0]["team2"]]).fetchall()
        assert rows == [("Football-Data.co.uk", 3, 3)]  # the published row is never overwritten
        assert con.execute("SELECT count(*) FROM recent_matches WHERE source=?",
                           [PROVISIONAL_SOURCE]).fetchone()[0] == len(played) - 1


def _txt_season(teams, undated_round=None):
    """A Football.TXT double round robin in both OpenFootball styles (scores before/after the away club)."""
    rounds = []
    for r in range(2 * (len(teams) - 1)):
        rotated = teams[:1] + teams[1:][r % (len(teams) - 1):] + teams[1:][:r % (len(teams) - 1)]
        pairs = list(zip(rotated[:len(teams) // 2], reversed(rotated[len(teams) // 2:])))
        rounds.append([(a, b) if r < len(teams) - 1 else (b, a) for a, b in pairs])
    lines = ["= Test League 2026/27", "# comment"]
    for number, pairs in enumerate(rounds, 1):
        lines.append(f"▪ Round {number}" + (" (datum TBC)" if number == undated_round else ""))
        if number != undated_round:
            day = date(2026, 8, 1) + timedelta(days=7 * number)
            lines.append(day.strftime("%a %b ") + str(day.day) + (" 2026" if number == 1 else ""))
        for index, (home, away) in enumerate(pairs):
            if number == 1 and index == 0:
                lines += [f"  20:00   {home}  2-1 (1-0)  {away}", "    (Scorer 12', Other 50'(p);", "     Third 88')"]
            else:
                lines.append(f"  --:--  {home}   v   {away}")
        lines += ["  (*) note that may move", ""]
    return "\n".join(lines)


def test_football_txt_reader_feeds_the_same_validation():
    from football_analysis.open_fixtures import football_txt_to_json

    teams = [f"Club {index}" for index in range(14)]
    full = normalize_open_schedule(football_txt_to_json(_txt_season(teams), 2026), "G1", 2026)
    assert len(full) == 182 and full.scored.sum() == 1
    assert full.loc[full.scored, ["home_goals", "away_goals"]].values.tolist() == [[2, 1]]
    assert full.match_date.min() == date(2026, 8, 8) and full.match_date.max().year == 2027  # Jan+ rolls the year
    with pytest.raises(ValueError, match="invalid date"):  # a round without a published date blocks the import
        normalize_open_schedule(football_txt_to_json(_txt_season(teams, undated_round=9), 2026), "G1", 2026)
    with pytest.raises(ValueError, match="Unrecognised"):
        football_txt_to_json("▪ Round 1\nSat Aug 8 2026\n  Club A against Club B", 2026)
