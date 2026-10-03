import sqlite3

from football_analysis import ingest as module
from football_analysis.adapters import normalize
from football_analysis.api.refresh import RefreshRunReport


def test_postgres_outage_queues_results_and_replays_once(tmp_path, monkeypatch):
    raw = b"Div,Date,HomeTeam,AwayTeam,FTHG,FTAG,FTR\nE0,17/08/2024,Arsenal,Chelsea,2,1,H\n"
    batch = normalize(raw, "E0", 2024, "test://results", require_complete=False)

    class Adapter:
        def fetch(self, league, year):
            return batch

    queue_path = tmp_path / "pending_matches.sqlite3"
    monkeypatch.setattr(module, "QUEUE_PATH", queue_path)
    monkeypatch.setenv("FOOTBALL_STORAGE_BACKEND", "postgres")
    monkeypatch.delenv("FOOTBALL_POSTGRES_DSN", raising=False)
    deferred = module.ingest(Adapter(), years=[2024], leagues=["E0"])
    assert deferred[0]["status"] == "deferred"
    report = RefreshRunReport()
    report.add(0, "Historical results", deferred, required=True)
    assert len(report.required_failures) == 1
    with sqlite3.connect(queue_path) as queue:
        assert queue.execute("SELECT count(*) FROM pending_matches").fetchone()[0] == 1

    local_db = tmp_path / "replay.duckdb"
    original_connect = module.connect
    monkeypatch.setattr(module, "connect", lambda _db: original_connect(local_db))
    applied = module.ingest(Adapter(), years=[2024], leagues=["E0"])
    assert applied[0]["status"] == "success"
    with original_connect(local_db) as con:
        assert con.execute("SELECT home_goals FROM matches").fetchone()[0] == 2
        assert con.execute("SELECT count(*) FROM elo_ratings").fetchone()[0] == 2
    with sqlite3.connect(queue_path) as queue:
        assert queue.execute("SELECT count(*) FROM pending_matches").fetchone()[0] == 0
