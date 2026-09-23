"""Free TheSportsDB reference standings adapter and sync command."""

import argparse
import time
from datetime import datetime, timedelta

import pandas as pd
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from .config import current_season, seasons
from .ingest import connect
from .sync_state import is_fresh, mark_fresh


LEAGUE_IDS = {"E0": 4328, "D1": 4331, "I1": 4332, "F1": 4334, "SP1": 4335}
SOURCE = "TheSportsDB"


class TheSportsDBStandings:
    base_url = "https://www.thesportsdb.com/api/v1/json/123/lookuptable.php"

    def __init__(self):
        self.session = requests.Session()
        self.session.headers["User-Agent"] = "football-analysis/0.4 (personal analytics)"
        retry = Retry(
            total=3, backoff_factor=1, status_forcelist=[429, 500, 502, 503, 504],
            respect_retry_after_header=True,
        )
        self.session.mount("https://", HTTPAdapter(max_retries=retry))

    def fetch(self, league, year):
        season_name = f"{year}-{year + 1}"
        response = self.session.get(
            self.base_url, params={"l": LEAGUE_IDS[league], "s": season_name}, timeout=(10, 45),
        )
        response.raise_for_status()
        payload = response.json().get("table") or []
        time.sleep(2.1)
        rows = []
        for item in payload:
            rows.append({
                "source": SOURCE, "league": league, "season": year,
                "rank": int(item["intRank"]), "team": item["strTeam"],
                "played": int(item["intPlayed"]), "points": int(item["intPoints"]),
                "goal_difference": int(item["intGoalDifference"]),
                "form": item.get("strForm") or "", "description": item.get("strDescription") or "",
                "source_updated_at": pd.to_datetime(item.get("dateUpdated"), errors="coerce"),
                "fetched_at": datetime.now(),
            })
        return pd.DataFrame(rows)


def sync(adapter=None, db=None, years=None, leagues=None, refresh=False):
    adapter = adapter or TheSportsDBStandings()
    report = []
    with connect(db) if db is not None else connect() as con:
        for year in years if years is not None else seasons():
            for league in leagues if leagues is not None else LEAGUE_IDS:
                key = f"standings:{league}:{year}"
                has_rows = con.execute(
                    "SELECT count(*) FROM reference_standings WHERE source=? AND league=? AND season=?",
                    [SOURCE, league, year],
                ).fetchone()[0] > 0
                max_age = (
                    timedelta(hours=6) if year >= current_season()
                    else None if has_rows else timedelta(days=1)
                )
                if not refresh and is_fresh(con, key, max_age):
                    report.append({"league": league, "season": year, "status": "cached"})
                    print(report[-1], flush=True)
                    continue
                try:
                    frame = adapter.fetch(league, year)
                    if not frame.empty:
                        con.register("incoming_reference", frame)
                    con.execute("BEGIN")
                    try:
                        con.execute("DELETE FROM reference_standings WHERE source=? AND league=? AND season=?", [SOURCE, league, year])
                        if not frame.empty:
                            con.execute("INSERT INTO reference_standings SELECT * FROM incoming_reference")
                        mark_fresh(con, key)
                        con.execute("COMMIT")
                    except Exception:
                        con.execute("ROLLBACK")
                        raise
                    finally:
                        if not frame.empty:
                            con.unregister("incoming_reference")
                    report.append({"league": league, "season": year, "status": "success", "rows": len(frame)})
                except Exception as exc:
                    report.append({"league": league, "season": year, "status": "failed", "detail": str(exc)})
                print(report[-1], flush=True)
    return report


def main():
    parser = argparse.ArgumentParser(description="Sync free top-five reference standings")
    parser.add_argument("--seasons", nargs="+", type=int)
    parser.add_argument("--leagues", nargs="+", choices=LEAGUE_IDS)
    parser.add_argument("--refresh", action="store_true", help="Bypass persisted freshness checks")
    args = parser.parse_args()
    result = sync(years=args.seasons, leagues=args.leagues, refresh=args.refresh)
    raise SystemExit(1 if any(row["status"] == "failed" for row in result) else 0)


if __name__ == "__main__":
    main()
