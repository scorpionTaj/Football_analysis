import argparse
import json
from importlib.resources import files
from uuid import uuid4
import duckdb
import pandas as pd
from .adapters import FootballDataCSV, LocalCSV
from .analytics import elo_history, team_match_rows, team_shot_efficiency
from .config import DATA, DB, LEAGUES, seasons
from .sync_state import cached_fingerprint, mark_fresh

def _store_batch(con, league, year, batch):
    count = len(batch.frame)
    key = f"historical-matches:{league}:{year}"
    existing_count = con.execute(
        "SELECT count(*) FROM matches WHERE league=? AND season=?", [league, year],
    ).fetchall()[0][0]
    if cached_fingerprint(con, key) == batch.digest and existing_count == count:
        mark_fresh(con, key, batch.digest)  # record the successful check, not only changes
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


def connect(db=DB):
    """DuckDB is the single writer; serving stores are filled by `football-publish`."""
    db.parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(db))
    con.execute(files("football_analysis").joinpath("schema.sql").read_text())
    return con


def _warehouse_elo(con, matches):
    """Elo from the model's own engine (ml.ml_elo_ratings, built by dbt), limited to the
    league-seasons the dashboard shows, so screen and model never disagree."""
    exists = con.execute("SELECT count(*) FROM information_schema.tables "
                         "WHERE table_schema = 'ml' AND table_name = 'ml_elo_ratings'").fetchall()[0][0]
    if not exists or matches.empty:
        return None
    con.register("dashboard_scope", matches[["league", "season"]].drop_duplicates())
    try:
        return con.sql("SELECT e.league, e.season, e.match_date, e.team, e.opponent, e.venue, "
                       "e.pre_elo, e.post_elo, e.elo_change FROM ml.ml_elo_ratings e "
                       "JOIN dashboard_scope USING (league, season)").df()
    finally:
        con.unregister("dashboard_scope")


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
    elo = _warehouse_elo(con, matches)
    if elo is None:  # before the first dbt build: legacy per-league engine
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
    with connect(db) as con:
        for league, year in partitions:
            run_id = str(uuid4())
            url, digest, count = "", "", 0
            try:
                batch = adapter.fetch(league, year)
                url, digest, count = batch.url, batch.digest, len(batch.frame)
                updated = _store_batch(con, league, year, batch)
                report.append(dict(league=league, season=year, status="success", rows=count,
                                   **({"unchanged": True} if not updated else {})))
                changed |= updated
            except Exception as exc:
                con.execute("INSERT INTO ingestion_runs VALUES (?, ?, ?, ?, ?, ?, 'failed', ?, current_timestamp)",
                            [run_id, league, year, url, digest, count, str(exc)])
                report.append(dict(league=league, season=year, status="failed", detail=str(exc)))
            print(json.dumps(report[-1]), flush=True)
        if changed:
            refresh_analytics(con)
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
