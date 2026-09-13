from football_analysis.players import _profile_frame, _stats_frame


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
