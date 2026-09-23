from football_analysis.event_details import detail_frames, sync_event_details
from football_analysis.ingest import connect


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


def test_event_details_cache_empty_provider_result(tmp_path):
    class Adapter:
        calls = 0

        def fetch(self, event_id):
            self.calls += 1
            return {"statistics": [], "timeline": [], "lineups": []}

    adapter = Adapter()
    db = tmp_path / "events.duckdb"
    assert sync_event_details(db=db, event_ids=["42"], adapter=adapter)[0]["status"] == "success"
    assert sync_event_details(db=db, event_ids=["42"], adapter=adapter)[0]["status"] == "cached"
    assert adapter.calls == 1


def test_event_details_respect_requested_league(tmp_path):
    class Adapter:
        seen = []

        def fetch(self, event_id):
            self.seen.append(event_id)
            return {"statistics": [], "timeline": [], "lineups": []}

    db = tmp_path / "scoped.duckdb"
    with connect(db) as con:
        con.execute("""
            INSERT INTO recent_events
                (event_id, league, season, match_date, home_team, away_team,
                 event_kind, source, fetched_at)
            VALUES ('e0', 'E0', 2026, '2026-09-01', 'Arsenal', 'Chelsea',
                    'past', 'test', current_timestamp),
                   ('sp1', 'SP1', 2026, '2026-09-01', 'Barcelona', 'Madrid',
                    'past', 'test', current_timestamp)
        """)
    adapter = Adapter()
    sync_event_details(db=db, leagues=["E0"], adapter=adapter)
    assert adapter.seen == ["e0"]
