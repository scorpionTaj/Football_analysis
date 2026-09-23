import pandas as pd

from football_analysis.reference_standings import sync as sync_standings
from football_analysis.sync_state import is_fresh, mark_fresh
from football_analysis.ingest import connect
from datetime import timedelta


def test_shared_freshness_gate(tmp_path):
    db = tmp_path / "fresh.duckdb"
    with connect(db) as con:
        assert not is_fresh(con, "example", timedelta(days=1))
        mark_fresh(con, "example")
        assert is_fresh(con, "example", timedelta(days=1))


def test_standings_skip_recently_checked_partition(tmp_path):
    class Adapter:
        calls = 0

        def fetch(self, league, year):
            self.calls += 1
            return pd.DataFrame()

    adapter = Adapter()
    db = tmp_path / "standings.duckdb"
    assert sync_standings(adapter=adapter, db=db, years=[2026], leagues=["E0"])[0]["status"] == "success"
    assert sync_standings(adapter=adapter, db=db, years=[2026], leagues=["E0"])[0]["status"] == "cached"
    assert adapter.calls == 1
