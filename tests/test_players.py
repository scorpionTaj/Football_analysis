from football_analysis.players import _profile_frame, _stats_frame
from football_analysis.players import sync_players
from football_analysis.ingest import connect


def test_player_profile_and_stats_normalization():
    profiles = _profile_frame([
        {
            "idPlayer": "7", "strPlayer": "Example Player", "strPosition": "Forward",
            "strNationality": "Testland", "dateBorn": "2000-02-03", "strNumber": "9",
        }
    ], "42", "Example FC")
    assert profiles.loc[0, "player"] == "Example Player"
    assert profiles.loc[0, "team"] == "Example FC"

    stats = _stats_frame([
        {
            "idTeam": "42", "strTeam": "Example FC", "strLeague": "Test League",
            "strSeason": "2025-2026", "strStatistic": "Goals", "strValue": "8",
        }
    ], "7")
    assert stats.loc[0, "value"] == 8


def test_non_numeric_player_stat_is_not_inferred():
    stats = _stats_frame([
        {
            "strLeague": "Test League", "strSeason": "2025-2026",
            "strStatistic": "Goals", "strValue": "unknown",
        }
    ], "7")
    assert stats.empty


def test_profile_refresh_preserves_stats_and_warm_sync_skips_provider(tmp_path):
    class Adapter:
        calls = 0
        stats_available = True

        def find_team(self, name):
            self.calls += 1
            return {"idTeam": "42", "strTeam": name}

        def players(self, team_id):
            return [{"idPlayer": "7", "strPlayer": "Example Player"}]

        def stats(self, player_id):
            return ([{"strLeague": "Test", "strSeason": "2025-2026",
                      "strStatistic": "Goals", "strValue": "8"}]
                    if self.stats_available else [])

    adapter = Adapter()
    db = tmp_path / "players.duckdb"
    assert sync_players(db=db, clubs=["Arsenal"], adapter=adapter)[0]["status"] == "success"
    assert sync_players(db=db, clubs=["Arsenal"], adapter=adapter)[0]["status"] == "cached"
    assert adapter.calls == 1
    assert sync_players(
        db=db, clubs=["Arsenal"], adapter=adapter, include_stats=False, refresh=True,
    )[0]["status"] == "success"
    adapter.stats_available = False
    assert sync_players(db=db, clubs=["Arsenal"], adapter=adapter, refresh=True)[0]["status"] == "success"
    with connect(db) as con:
        assert con.execute("SELECT count(*) FROM player_stats").fetchall()[0][0] == 1
