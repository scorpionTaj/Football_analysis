import argparse
import json
from importlib.resources import files
from uuid import uuid4
import duckdb
from .adapters import FootballDataCSV, LocalCSV
from .config import DATA, DB, LEAGUES, seasons

def connect(db=DB):
    db.parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(db))
    con.execute(files("football_analysis").joinpath("schema.sql").read_text())
    return con

def ingest(adapter, db=DB, years=None, leagues=None):
    report = []
    with connect(db) as con:
        for year in years if years is not None else seasons():
            for league in leagues if leagues is not None else LEAGUES:
                run_id = str(uuid4())
                url, digest, count = "", "", 0
                try:
                    batch = adapter.fetch(league, year)
                    url, digest, count = batch.url, batch.digest, len(batch.frame)
                    con.register("incoming", batch.frame)
                    con.execute("BEGIN")
                    try:
                        con.execute("DELETE FROM matches WHERE league=? AND season=?", [league, year])
                        con.execute("INSERT INTO matches SELECT * FROM incoming")
                        con.execute("INSERT INTO ingestion_runs VALUES (?, ?, ?, ?, ?, ?, 'success', '', current_timestamp)", [run_id, league, year, url, digest, count])
                        con.execute("COMMIT")
                    except Exception:
                        con.execute("ROLLBACK")
                        raise
                    finally:
                        con.unregister("incoming")
                    report.append(dict(league=league, season=year, status="success", rows=count))
                except Exception as exc:
                    con.execute("INSERT INTO ingestion_runs VALUES (?, ?, ?, ?, ?, ?, 'failed', ?, current_timestamp)", [run_id, league, year, url, digest, count, str(exc)])
                    report.append(dict(league=league, season=year, status="failed", detail=str(exc)))
                print(json.dumps(report[-1]), flush=True)
    return report

def main():
    parser = argparse.ArgumentParser(description="Ingest complete seasons from free public CSVs")
    parser.add_argument("--refresh", action="store_true")
    parser.add_argument("--offline", type=str, help="Replay a raw CSV directory without network")
    parser.add_argument("--seasons", nargs="+", type=int, help="Season start years; defaults to latest five completed")
    parser.add_argument("--leagues", nargs="+", choices=LEAGUES)
    args = parser.parse_args()
    adapter = LocalCSV(args.offline) if args.offline else FootballDataCSV(DATA / "raw", args.refresh)
    results = ingest(adapter, years=args.seasons, leagues=args.leagues)
    raise SystemExit(1 if any(r["status"] == "failed" for r in results) else 0)

if __name__ == "__main__":
    main()
