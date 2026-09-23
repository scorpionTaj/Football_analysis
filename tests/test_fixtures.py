from datetime import date, timedelta

from football_analysis.api.db import ReadOnlyStore
from football_analysis.api.queries import list_matches
from football_analysis.fixtures import normalize_fixtures, sync_fixtures
from football_analysis.ingest import connect
from football_analysis.prediction_features import load_match_inputs


class StaticFixtureAdapter:
    def __init__(self, raw: bytes):
        self.raw = raw

    def fetch(self) -> bytes:
        return self.raw


def test_fixture_parser_rejects_html_and_filters_stale_rows():
    today = date(2026, 9, 23)
    raw = b"Div,Date,Time,HomeTeam,AwayTeam\nE0,24/09/2026,20:00,Arsenal,Liverpool\nE0,20/09/2026,18:00,Chelsea,Arsenal\nSP1,24/09/2026,21:00,Barcelona,Real Madrid\n"
    rows = normalize_fixtures(raw, 2026, ["E0"], today)
    assert len(rows) == 1
    assert rows.iloc[0].Time == "20:00"
    try:
        normalize_fixtures(b"<html>blocked</html>", 2026, ["E0"], today)
    except ValueError:
        pass
    else:
        raise AssertionError("HTML was accepted as a fixture CSV")


def test_weekly_fixtures_are_reconciled_and_searchable_before_pagination(tmp_path):
    today = date.today()
    season = today.year if today.month >= 7 else today.year - 1
    fixture_day = today + timedelta(days=1)
    if fixture_day > date(season + 1, 6, 30):
        return
    raw = (
        "Div,Date,Time,HomeTeam,AwayTeam\n"
        f"E0,{fixture_day:%d/%m/%Y},19:45,Arsenal,Liverpool\n"
        f"E0,{fixture_day:%d/%m/%Y},18:00,Unknown Club,Chelsea\n"
    ).encode()
    db = tmp_path / "fixtures.duckdb"
    with connect(db) as con:
        con.execute(
            "INSERT INTO recent_matches (league, season, match_date, home_team, away_team, "
            "home_goals, away_goals, source, fetched_at) VALUES "
            "('E0', ?, ?, 'Arsenal', 'Chelsea', 2, 0, 'test', current_timestamp), "
            "('E0', ?, ?, 'Liverpool', 'Arsenal', 1, 1, 'test', current_timestamp)",
            [season, today - timedelta(days=7), season, today - timedelta(days=14)],
        )
    report = sync_fixtures(db, season=season, leagues=["E0"], adapter=StaticFixtureAdapter(raw), today=today)
    assert report == {"status": "success", "rows": 1, "unmapped": 1}
    with connect(db) as con:
        _, upcoming = load_match_inputs(con)
    assert len(upcoming) == 1
    assert upcoming.iloc[0].home_team == "Arsenal"
    store = ReadOnlyStore(db)
    try:
        result = list_matches(store, competition="E0", season=season, limit=1, query="Livrpool")
        assert result.page.returned == 1
        assert result.matches[0].away.name == "Liverpool"
        assert result.matches[0].kickoff_time == "19:45"
    finally:
        store.close()


def test_weekly_fixture_supersedes_a_rescheduled_next_event(tmp_path):
    today = date.today()
    season = today.year if today.month >= 7 else today.year - 1
    fixture_day = today + timedelta(days=1)
    if fixture_day > date(season + 1, 6, 30):
        return
    db = tmp_path / "rescheduled.duckdb"
    with connect(db) as con:
        con.execute(
            "INSERT INTO recent_events (event_id, league, season, match_date, home_team, away_team, "
            "event_kind, source, fetched_at) VALUES "
            "('old-next', 'E0', ?, ?, 'Arsenal', 'Liverpool', 'next', 'test', current_timestamp), "
            "('new-fixture', 'E0', ?, ?, 'Arsenal', 'Liverpool', 'fixture', 'test', current_timestamp)",
            [season, fixture_day + timedelta(days=7), season, fixture_day],
        )
    store = ReadOnlyStore(db)
    try:
        result = list_matches(store, competition="E0", season=season)
        assert len(result.matches) == 1
        assert result.matches[0].match_date == fixture_day
    finally:
        store.close()
    with connect(db) as con:
        con.execute(
            "INSERT INTO recent_matches (league, season, match_date, home_team, away_team, "
            "home_goals, away_goals, source, fetched_at) VALUES "
            "('E0', ?, ?, 'Arsenal', 'Liverpool', 2, 1, 'test', current_timestamp)",
            [season, today],
        )
    store = ReadOnlyStore(db)
    try:
        result = list_matches(store, competition="E0", season=season)
        assert len(result.matches) == 1
        assert result.matches[0].home_goals == 2
    finally:
        store.close()


def test_match_list_pages_near_future_before_distant_schedule(tmp_path):
    today = date.today()
    season = today.year if today.month >= 7 else today.year - 1
    if today + timedelta(days=31) > date(season + 1, 6, 30):
        return
    db = tmp_path / "calendar-order.duckdb"
    with connect(db) as con:
        con.execute(
            "INSERT INTO recent_events (event_id, league, season, match_date, home_team, away_team, "
            "event_kind, source, fetched_at) VALUES "
            "('distant', 'E0', ?, ?, 'Chelsea', 'Liverpool', 'fixture', 'test', current_timestamp), "
            "('near', 'E0', ?, ?, 'Arsenal', 'Everton', 'fixture', 'test', current_timestamp)",
            [season, today + timedelta(days=30), season, today + timedelta(days=1)],
        )
        con.execute(
            "INSERT INTO recent_matches (league, season, match_date, home_team, away_team, "
            "home_goals, away_goals, source, fetched_at) VALUES "
            "('E0', ?, ?, 'Fulham', 'Brentford', 1, 0, 'test', current_timestamp)",
            [season, today - timedelta(days=1)],
        )
    store = ReadOnlyStore(db)
    try:
        first = list_matches(store, competition="E0", season=season, limit=1)
        second = list_matches(store, competition="E0", season=season, cursor=first.page.next_cursor, limit=1)
        third = list_matches(store, competition="E0", season=season, cursor=second.page.next_cursor, limit=1)
        assert [page.matches[0].home.name for page in (first, second, third)] == [
            "Arsenal", "Chelsea", "Fulham",
        ]
        assert third.page.next_cursor is None
    finally:
        store.close()
