import json

import pandas as pd

from football_analysis.ingest import connect
from football_analysis.tournaments import (
    TournamentBatch,
    parse_champions_league,
    parse_world_cup,
    sync_tournaments,
)


def test_champions_league_parser_tracks_stage_and_implied_year():
    raw = """= UEFA Champions League 2025/26
▪ League, Matchday 1
  Tue Sep 16 2025
    18:45  Athletic Club (ESP) v Arsenal FC (ENG) 0-2 (0-0)
▪ Quarter-finals, Matchday 1
  Tue Apr 7
    Real Madrid CF (ESP) v FC Bayern München (GER) 3-1 (1-0)
""".encode()
    batch = parse_champions_league(raw, 2025)
    assert len(batch.frame) == 2
    assert batch.frame.iloc[0].away_team == "Arsenal FC"
    assert batch.frame.iloc[1].match_date == pd.Timestamp("2026-04-07").date()
    assert batch.frame.iloc[1].stage == "Quarter-finals, Matchday 1"


def test_world_cup_parser_preserves_neutral_stage_and_penalties():
    raw = json.dumps({"matches": [{
        "round": "Round of 16", "date": "2026-07-01",
        "team1": "Morocco", "team2": "Spain", "ground": "Atlanta",
        "score": {"ft": [1, 1], "et": [2, 2], "p": [5, 4]},
        "goals1": [{"name": "Player One", "minute": "90+2", "penalty": True}],
    }]}).encode()
    frame = parse_world_cup(raw, 2026).frame
    assert frame.loc[0, "neutral"]
    assert frame.loc[0, "home_goals"] == 2
    assert frame.loc[0, "home_penalties"] == 5
    assert len(parse_world_cup(raw, 2026).goals) == 1
    assert parse_world_cup(raw, 2026).goals.loc[0, "penalty"]


def test_club_world_cup_parser_uses_its_own_competition_code():
    raw = json.dumps({"matches": [{
        "round": "Final", "date": "2025-07-13",
        "team1": "Chelsea FC", "team2": "Paris Saint-Germain FC",
        "score": {"ft": [3, 0]},
    }]}).encode()
    batch = parse_world_cup(raw, 2025, competition="CWC")
    assert batch.frame.loc[0, "competition"] == "CWC"
    assert batch.frame.loc[0, "neutral"]


def test_sync_replaces_only_requested_partition(tmp_path):
    columns = [
        "competition", "season", "stage", "group_name", "match_date",
        "home_team", "away_team", "home_goals", "away_goals",
        "home_penalties", "away_penalties", "venue", "neutral", "status",
        "source", "source_url", "fetched_at",
    ]

    class Stub:
        def __init__(self):
            self.score = 1

        def fetch(self, competition, season):
            values = [[
                competition, season, "Final", "", pd.Timestamp("2026-05-30").date(),
                "Club A", "Club B", self.score, 0, None, None, "", False,
                "FINISHED", "test", "memory", pd.Timestamp("2026-06-01"),
            ]]
            return TournamentBatch(pd.DataFrame(values, columns=columns), "memory", "hash")

    db = tmp_path / "football.duckdb"
    adapter = Stub()
    assert sync_tournaments(db, [("UCL", 2025)], adapter)[0]["status"] == "success"
    adapter.score = 2
    assert sync_tournaments(db, [("UCL", 2025)], adapter)[0]["status"] == "success"
    with connect(db) as con:
        assert con.execute("SELECT count(*), max(home_goals) FROM tournament_matches").fetchall()[0] == (1, 2)


def test_running_editions_are_redownloaded_daily_and_completed_ones_never(tmp_path, monkeypatch):
    import os
    import time

    from football_analysis import tournaments

    calls = []

    class Session:
        def get(self, url, timeout):
            calls.append(url)
            raise RuntimeError("network used")

    adapter = tournaments.OpenFootballTournaments(cache=tmp_path, session=Session())
    monkeypatch.setattr(tournaments, "parse_champions_league", lambda raw, year, url: raw)
    for season in (2022, tournaments.current_season()):
        path = tmp_path / "ucl" / f"{season}.txt"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"cached")
        old = time.time() - 2 * 86400
        os.utime(path, (old, old))
    assert adapter.fetch("UCL", 2022) == b"cached" and not calls
    try:
        adapter.fetch("UCL", tournaments.current_season())
    except RuntimeError:
        pass
    assert len(calls) == 1 and tournaments.current_season() in tournaments.UCL_SEASONS
