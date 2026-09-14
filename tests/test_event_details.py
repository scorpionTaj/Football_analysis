from football_analysis.event_details import detail_frames


def test_event_detail_frames_keep_capped_source_values():
    statistics, timeline, lineups = detail_frames("42", {
        "statistics": [{"strStat": "Blocked Shots", "intHome": "4", "intAway": "3"}],
        "timeline": [{
            "idTimeline": "9", "intTime": "60", "strTimeline": "Goal",
            "strTimelineDetail": "Normal Goal", "strTeam": "Arsenal",
            "idPlayer": "8", "strPlayer": "Player One", "strAssist": "Player Two",
            "strHome": "Yes", "strComment": "NULL",
        }],
        "lineups": [{
            "idLineup": "7", "strTeam": "Arsenal", "idPlayer": "8",
            "strPlayer": "Player One", "strPosition": "Forward", "strHome": "Yes",
            "strSubstitute": "No", "intSquadNumber": "10", "strCutout": "https://example.test/p.png",
        }],
    })
    assert statistics.loc[0, "home_value"] == 4
    assert timeline.loc[0, "event_type"] == "Goal"
    assert timeline.loc[0, "comment"] == ""
    assert lineups.loc[0, "is_substitute"] == False
