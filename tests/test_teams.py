from football_analysis.teams import display_team, team_key


def test_provider_aliases_share_one_club_identity():
    assert display_team("Man City") == "Manchester City"
    assert team_key("Man City") == team_key("Manchester City")
    assert team_key("Ath Madrid") == team_key("Atlético Madrid")
    assert team_key("Milan") == team_key("AC Milan")


def test_unknown_team_name_is_preserved():
    assert display_team("Example United") == "Example United"
