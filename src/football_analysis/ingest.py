import argparse
import json
import os
import sqlite3
from io import StringIO
from importlib.resources import files
from uuid import uuid4
import duckdb
import pandas as pd
from .adapters import Batch, FootballDataCSV, LocalCSV
from .analytics import elo_history, team_match_rows, team_shot_efficiency
from .config import DATA, DB, LEAGUES, seasons
from .sync_state import cached_fingerprint, mark_fresh

QUEUE_PATH = DATA / "pending_matches.sqlite3"


def _connection_unavailable(exc, db):
    if os.environ.get("FOOTBALL_STORAGE_BACKEND") != "postgres" or db != DB:
        return False
    from psycopg import OperationalError

    return isinstance(exc, OperationalError) or str(exc) == "FOOTBALL_POSTGRES_DSN is required for PostgreSQL writes"


def _queue_batch(league, year, batch):
    QUEUE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(QUEUE_PATH) as queue:
        queue.execute(
            "CREATE TABLE IF NOT EXISTS pending_matches ("
            "league TEXT NOT NULL, season INTEGER NOT NULL, url TEXT NOT NULL, "
            "digest TEXT NOT NULL, rows_json TEXT NOT NULL, "
            "PRIMARY KEY (league, season))"
        )
        queue.execute(
            "INSERT OR REPLACE INTO pending_matches VALUES (?, ?, ?, ?, ?)",
            [league, year, batch.url, batch.digest,
             batch.frame.to_json(orient="records", date_format="iso")],
        )


def _store_batch(con, league, year, batch):
    count = len(batch.frame)
    key = f"historical-matches:{league}:{year}"
    existing_count = con.execute(
        "SELECT count(*) FROM matches WHERE league=? AND season=?", [league, year],
    ).fetchone()[0]
    if cached_fingerprint(con, key) == batch.digest and existing_count == count:
        return False
    con.register("incoming", batch.frame)
    con.execute("BEGIN")
    try:
        con.execute("DELETE FROM matches WHERE league=? AND season=?", [league, year])
        con.execute("INSERT INTO matches SELECT * FROM incoming")
        con.execute(
            "INSERT INTO ingestion_runs VALUES (?, ?, ?, ?, ?, ?, 'success', '', current_timestamp)",
            [str(uuid4()), league, year, batch.url, batch.digest, count],
        )
        mark_fresh(con, key, batch.digest)
        con.execute("COMMIT")
    except Exception:
        con.execute("ROLLBACK")
        raise
    finally:
        con.unregister("incoming")
    return True


def _drain_queue(con):
    if not QUEUE_PATH.exists():
        return
    with sqlite3.connect(QUEUE_PATH) as queue:
        records = queue.execute(
            "SELECT league, season, url, digest, rows_json FROM pending_matches ORDER BY season, league"
        ).fetchall()
        for league, year, url, digest, rows_json in records:
            frame = pd.read_json(StringIO(rows_json), orient="records")
            frame["match_date"] = pd.to_datetime(frame.match_date).dt.date
            _store_batch(con, league, year, Batch(frame, url, digest))
        if records:
            refresh_analytics(con)
            queue.executemany(
                "DELETE FROM pending_matches WHERE league=? AND season=?",
                [(league, year) for league, year, *_ in records],
            )

def connect(db=DB):
    if os.environ.get("FOOTBALL_STORAGE_BACKEND") == "postgres" and db == DB:
        from .postgres_write import PostgresWriteStore

        return PostgresWriteStore(
            os.environ.get("FOOTBALL_POSTGRES_DSN", ""),
            os.environ.get("FOOTBALL_POSTGRES_SCHEMA", "football_analysis_next"),
        )
    db.parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(db))
    con.execute(files("football_analysis").joinpath("schema.sql").read_text())
    return con


def refresh_analytics(con):
    """Rebuild persisted analytics from the committed match store atomically."""
    matches = con.sql("SELECT * FROM matches").df()
    tables = {row[0] for row in con.sql("SHOW TABLES").fetchall()}
    if "recent_matches" in tables:
        current = con.sql(
            "SELECT league, season, match_date, home_team, away_team, home_goals, away_goals, "
            "home_shots, away_shots, home_sot, away_sot FROM recent_matches"
        ).df()
        if not current.empty:
            matches = pd.concat([matches, current], ignore_index=True).drop_duplicates(
                ["league", "season", "home_team", "away_team"], keep="last",
            )
    team_matches = team_match_rows(matches)
    elo = elo_history(matches)
    shots = team_shot_efficiency(team_matches)
    con.register("incoming_elo", elo)
    con.register("incoming_shots", shots)
    con.execute("BEGIN")
    try:
        con.execute("DELETE FROM elo_ratings")
        con.execute("INSERT INTO elo_ratings SELECT * FROM incoming_elo")
        con.execute("DELETE FROM shot_efficiency_cache")
        con.execute("INSERT INTO shot_efficiency_cache SELECT * FROM incoming_shots")
        con.execute("DELETE FROM analytics_metadata WHERE cache_key='match_analytics'")
        con.execute(
            "INSERT INTO analytics_metadata VALUES ('match_analytics', current_timestamp, ?)",
            [len(matches)],
        )
        con.execute("COMMIT")
    except Exception:
        con.execute("ROLLBACK")
        raise
    finally:
        con.unregister("incoming_elo")
        con.unregister("incoming_shots")


def refresh_analytics_cache(db=DB):
    with connect(db) as con:
        refresh_analytics(con)

def ingest(adapter, db=DB, years=None, leagues=None):
    report = []
    changed = False
    partitions = [(league, year) for year in (years if years is not None else seasons())
                  for league in (leagues if leagues is not None else LEAGUES)]
    try:
        con = connect(db)
    except Exception as exc:
        if not _connection_unavailable(exc, db):
            raise
        for league, year in partitions:
            try:
                batch = adapter.fetch(league, year)
                _queue_batch(league, year, batch)
                row = dict(league=league, season=year, status="deferred", rows=len(batch.frame),
                           detail="Stored locally; PostgreSQL is unavailable")
            except Exception as fetch_exc:
                row = dict(league=league, season=year, status="failed", detail=str(fetch_exc))
            report.append(row)
            print(json.dumps(row), flush=True)
        return report
    with con:
        if os.environ.get("FOOTBALL_STORAGE_BACKEND") == "postgres" and db == DB:
            _drain_queue(con)
        offline = False
        last_batch = None
        for league, year in partitions:
            run_id = str(uuid4())
            url, digest, count = "", "", 0
            try:
                batch = adapter.fetch(league, year)
                last_batch = (league, year, batch)
                url, digest, count = batch.url, batch.digest, len(batch.frame)
                if offline:
                    _queue_batch(league, year, batch)
                    report.append(dict(league=league, season=year, status="deferred", rows=count,
                                       detail="Stored locally; PostgreSQL is unavailable"))
                    print(json.dumps(report[-1]), flush=True)
                    continue
                updated = _store_batch(con, league, year, batch)
                report.append(dict(league=league, season=year, status="success", rows=count,
                                   **({"unchanged": True} if not updated else {})))
                changed |= updated
            except Exception as exc:
                if _connection_unavailable(exc, db) and count:
                    try:
                        _queue_batch(league, year, batch)
                        offline = True
                        report.append(dict(league=league, season=year, status="deferred", rows=count,
                                           detail="Stored locally; PostgreSQL connection was lost"))
                    except Exception as queue_exc:
                        report.append(dict(league=league, season=year, status="failed", detail=str(queue_exc)))
                else:
                    if not offline:
                        con.execute("INSERT INTO ingestion_runs VALUES (?, ?, ?, ?, ?, ?, 'failed', ?, current_timestamp)", [run_id, league, year, url, digest, count, str(exc)])
                    report.append(dict(league=league, season=year, status="failed", detail=str(exc)))
            print(json.dumps(report[-1]), flush=True)
        if changed and not offline:
            try:
                refresh_analytics(con)
            except Exception as exc:
                if not _connection_unavailable(exc, db) or last_batch is None:
                    raise
                _queue_batch(*last_batch)
                report.append(dict(league=last_batch[0], season=last_batch[1], status="deferred",
                                   detail="Results saved; analytics queued for retry"))
    return report

def main():
    parser = argparse.ArgumentParser(description="Ingest complete seasons from free public CSVs")
    parser.add_argument("--refresh", action="store_true")
    parser.add_argument("--offline", type=str, help="Replay a raw CSV directory without network")
    parser.add_argument("--seasons", nargs="+", type=int, help="Season start years; defaults to latest five completed")
    parser.add_argument("--leagues", nargs="+", choices=LEAGUES)
    parser.add_argument(
        "--analytics-only", action="store_true",
        help="Rebuild persisted Elo and shot analytics without fetching source data",
    )
    args = parser.parse_args()
    if args.analytics_only:
        refresh_analytics_cache()
        return
    adapter = LocalCSV(args.offline) if args.offline else FootballDataCSV(DATA / "raw", args.refresh)
    results = ingest(adapter, years=args.seasons, leagues=args.leagues)
    raise SystemExit(1 if any(r["status"] != "success" for r in results) else 0)

if __name__ == "__main__":
    main()
