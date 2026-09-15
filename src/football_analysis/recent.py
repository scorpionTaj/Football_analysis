"""Free current-season match and event ingestion."""

import argparse
import time
from datetime import datetime

import pandas as pd
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from .adapters import FootballDataCSV
from .config import DATA, DB, RECENT_LEAGUES, THESPORTSDB_LEAGUE_IDS, current_season
from .ingest import connect, refresh_analytics


SOURCE_CSV = "Football-Data.co.uk"
SOURCE_EVENTS = "TheSportsDB"
EVENT_COLUMNS = [
    "event_id", "league", "season", "match_date", "home_team", "away_team",
    "home_goals", "away_goals", "status", "event_kind", "source", "fetched_at",
    "kickoff_time", "venue", "home_coach", "away_coach", "home_formation",
    "away_formation", "referee", "attendance",
]


def _first_present(item, *keys):
    return next((item.get(key) for key in keys if item.get(key)), None)


class TheSportsDBRecentEvents:
    base_url = "https://www.thesportsdb.com/api/v1/json/123"

    def __init__(self):
        self.session = requests.Session()
        self.session.headers["User-Agent"] = "football-analysis/0.4 (personal analytics)"
        retry = Retry(
            total=3, backoff_factor=1, status_forcelist=[429, 500, 502, 503, 504],
            respect_retry_after_header=True,
        )
        self.session.mount("https://", HTTPAdapter(max_retries=retry))

    def fetch(self, league, event_kind):
        endpoint = "eventspastleague.php" if event_kind == "past" else "eventsnextleague.php"
        response = self.session.get(
            f"{self.base_url}/{endpoint}",
            params={"id": THESPORTSDB_LEAGUE_IDS[league]}, timeout=(10, 45),
        )
        response.raise_for_status()
        rows = []
        for item in response.json().get("events") or []:
            season_text = item.get("strSeason") or ""
            try:
                season = int(season_text[:4])
            except ValueError:
                season = current_season()
            rows.append({
                "event_id": item["idEvent"], "league": league, "season": season,
                "match_date": pd.to_datetime(item["dateEvent"]).date(),
                "home_team": item.get("strHomeTeam") or "",
                "away_team": item.get("strAwayTeam") or "",
                "home_goals": pd.to_numeric(item.get("intHomeScore"), errors="coerce"),
                "away_goals": pd.to_numeric(item.get("intAwayScore"), errors="coerce"),
                "status": item.get("strStatus") or "",
                "event_kind": event_kind, "source": SOURCE_EVENTS,
                "fetched_at": datetime.now(),
                "kickoff_time": item.get("strTime") or None,
                "venue": item.get("strVenue") or None,
                "home_coach": _first_present(item, "strHomeTeamManager", "strHomeManager", "strHomeCoach"),
                "away_coach": _first_present(item, "strAwayTeamManager", "strAwayManager", "strAwayCoach"),
                "home_formation": item.get("strHomeFormation") or None,
                "away_formation": item.get("strAwayFormation") or None,
                "referee": item.get("strReferee") or None,
                "attendance": pd.to_numeric(item.get("intSpectators"), errors="coerce"),
            })
        time.sleep(2.1)
        return pd.DataFrame(rows)


def sync_recent(db=DB, year=None, leagues=None, refresh=True, event_adapter=None):
    year = year if year is not None else current_season()
    leagues = leagues if leagues is not None else list(RECENT_LEAGUES)
    match_adapter = FootballDataCSV(DATA / "raw", refresh=refresh, require_complete=False)
    event_adapter = event_adapter or TheSportsDBRecentEvents()
    report = []
    with connect(db) as con:
        for league in leagues:
            try:
                batch = match_adapter.fetch(league, year)
                frame = batch.frame.copy()
                frame["source"] = SOURCE_CSV
                frame["fetched_at"] = datetime.now()
                con.register("incoming_recent", frame)
                con.execute("BEGIN")
                try:
                    con.execute("DELETE FROM recent_matches WHERE league=? AND season=?", [league, year])
                    con.execute(
                        """INSERT INTO recent_matches (
                            league, season, match_date, home_team, away_team,
                            home_goals, away_goals, home_shots, away_shots, home_sot, away_sot,
                            half_time_home_goals, half_time_away_goals,
                            home_corners, away_corners, home_fouls, away_fouls,
                            home_yellows, away_yellows, home_reds, away_reds, referee,
                            source, fetched_at
                        ) SELECT * FROM incoming_recent"""
                    )
                    con.execute("COMMIT")
                except Exception:
                    con.execute("ROLLBACK")
                    raise
                finally:
                    con.unregister("incoming_recent")
                report.append({"league": league, "season": year, "status": "success", "rows": len(frame)})
            except Exception as exc:
                report.append({"league": league, "season": year, "status": "failed", "detail": str(exc)})
            print(report[-1], flush=True)

        for league in leagues:
            for event_kind in ("past", "next"):
                try:
                    frame = event_adapter.fetch(league, event_kind)
                    if not frame.empty:
                        for column in EVENT_COLUMNS:
                            if column not in frame:
                                frame[column] = None
                        frame = frame[EVENT_COLUMNS]
                        con.register("incoming_events", frame)
                        con.execute("BEGIN")
                        try:
                            event_ids = frame.event_id.astype(str).tolist()
                            if event_ids:
                                con.execute(
                                    f"DELETE FROM recent_events WHERE event_id IN ({','.join('?' for _ in event_ids)})",
                                    event_ids,
                                )
                            con.execute(
                                "DELETE FROM recent_events WHERE league=? AND event_kind=?",
                                [league, event_kind],
                            )
                            con.execute(
                                f"INSERT INTO recent_events ({', '.join(EVENT_COLUMNS)}) "
                                f"SELECT {', '.join(EVENT_COLUMNS)} FROM incoming_events"
                            )
                            con.execute("COMMIT")
                        except Exception:
                            con.execute("ROLLBACK")
                            raise
                        finally:
                            con.unregister("incoming_events")
                except Exception as exc:
                    print({"league": league, "event_kind": event_kind, "status": "failed", "detail": str(exc)}, flush=True)
        if any(row["status"] == "success" for row in report):
            refresh_analytics(con)
    return report


def main():
    parser = argparse.ArgumentParser(description="Sync current-season matches from free sources")
    parser.add_argument("--season", type=int)
    parser.add_argument("--leagues", nargs="+", choices=RECENT_LEAGUES)
    parser.add_argument("--cached", action="store_true", help="Use cached CSVs instead of redownloading")
    args = parser.parse_args()
    result = sync_recent(year=args.season, leagues=args.leagues, refresh=not args.cached)
    raise SystemExit(1 if any(row["status"] == "failed" for row in result) else 0)


if __name__ == "__main__":
    main()
