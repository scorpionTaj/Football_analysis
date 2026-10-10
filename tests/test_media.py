import pandas as pd
import pytest

from football_analysis.ingest import connect
from football_analysis.media import _competition_media_frame, _team_media_frame, discover_missing_clubs, sync_media


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


def test_media_backfill_saves_batches_and_skips_cached_misses(tmp_path):
    db = tmp_path / "football.duckdb"

    class InterruptingAdapter:
        def find_team(self, name):
            if name == "Chelsea":
                raise KeyboardInterrupt()
            if name == "Missing Town":
                return None
            return {"idTeam": "1", "strTeam": name, "strBadge": "https://example.test/badge.png"}

    with pytest.raises(KeyboardInterrupt):
        sync_media(
            db=db, clubs=["Arsenal", "Missing Town", "Chelsea"], leagues=[],
            adapter=InterruptingAdapter(), batch_size=10,
        )

    with connect(db) as con:
        assert con.execute("SELECT team FROM team_media").fetchall() == [("Arsenal",)]
        assert con.execute("SELECT team FROM media_lookup_cache WHERE status='not_found'").fetchall() == [("Missing Town",)]

    class ResumeAdapter:
        def __init__(self):
            self.calls = []

        def find_team(self, name):
            self.calls.append(name)
            return {"idTeam": "2", "strTeam": name, "strBadge": "https://example.test/badge.png"}

    adapter = ResumeAdapter()
    report = sync_media(
        db=db, clubs=["Arsenal", "Missing Town", "Chelsea"], leagues=[],
        adapter=adapter, batch_size=2,
    )
    assert adapter.calls == ["Chelsea"]
    assert [row["status"] for row in report] == ["cached", "cached_missing", "success"]
    with connect(db) as con:
        assert con.execute("SELECT count(*) FROM team_media").fetchone()[0] == 2


def test_competition_logos_cover_every_tournament_without_adding_event_syncs(tmp_path):
    from football_analysis.config import COMPETITIONS, THESPORTSDB_BADGE_IDS, THESPORTSDB_LEAGUE_IDS

    # Logo-only ids must not leak into the ids that drive provider event syncs.
    assert set(THESPORTSDB_LEAGUE_IDS) <= set(THESPORTSDB_BADGE_IDS)
    assert "EURO" in THESPORTSDB_BADGE_IDS and "EURO" not in THESPORTSDB_LEAGUE_IDS
    assert set(THESPORTSDB_BADGE_IDS) <= set(COMPETITIONS)

    class LeagueAdapter:
        def __init__(self):
            self.calls = []

        def league(self, league_id):
            self.calls.append(league_id)
            return {"idLeague": str(league_id), "strLeague": "x", "strBadge": f"https://example.test/{league_id}.png"}

    adapter = LeagueAdapter()
    sync_media(db=tmp_path / "football.duckdb", clubs=[], adapter=adapter)  # default: every logo id
    assert sorted(adapter.calls) == sorted(THESPORTSDB_BADGE_IDS.values())
    again = LeagueAdapter()
    sync_media(db=tmp_path / "football.duckdb", clubs=[], adapter=again)
    assert again.calls == []  # cached logos are never requested twice
