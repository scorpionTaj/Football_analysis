import pandas as pd

from football_analysis.ingest import connect
from football_analysis.media import _competition_media_frame, _team_media_frame, discover_missing_clubs


def test_team_media_uses_canonical_team_and_provider_artwork():
    frame = _team_media_frame([
        {
            "team": "FC Barcelona",
            "provider": {
                "idTeam": "1",
                "strTeam": "Barcelona",
                "strBadge": "https://example.test/barcelona.png",
            },
        }
    ])
    assert frame.loc[0, "team"] == "FC Barcelona"
    assert frame.loc[0, "badge_url"].endswith("barcelona.png")


def test_competition_media_keeps_internal_league_code():
    frame = _competition_media_frame([
        {
            "league_code": "E0",
            "league": "Premier League",
            "provider": {
                "idLeague": "4328",
                "strLeague": "English Premier League",
                "strBadge": "https://example.test/premier-league.png",
            },
        }
    ])
    assert frame.loc[0, "league_code"] == "E0"
    assert frame.loc[0, "league"] == "Premier League"


def test_discover_missing_clubs_compares_canonical_names(tmp_path):
    db = tmp_path / "football.duckdb"
    with connect(db) as con:
        con.execute("INSERT INTO team_media VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", [
            "test", "1", "Manchester City", "badge", "", "", "", "", pd.Timestamp("2026-09-14"),
        ])
        con.execute("INSERT INTO matches (league, season, match_date, home_team, away_team, home_goals, away_goals) VALUES (?, ?, ?, ?, ?, ?, ?)", [
            "E0", 2026, pd.Timestamp("2026-09-14"), "Man City", "Arsenal", 1, 0,
        ])
    assert discover_missing_clubs(db) == ["Arsenal"]
