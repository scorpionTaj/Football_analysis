from football_analysis.media import _competition_media_frame, _team_media_frame


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
