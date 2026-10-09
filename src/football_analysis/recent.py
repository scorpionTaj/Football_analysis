"""Free current-season match and event ingestion."""

import argparse
import time
from datetime import date, datetime, timedelta

import pandas as pd
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from .adapters import FootballDataCSV
from .config import (
    CALENDAR_YEAR_TOURNAMENTS,
    DATA,
    DB,
    RECENT_LEAGUES,
    THESPORTSDB_LEAGUE_IDS,
    TOURNAMENTS,
    current_season,
)
from .ingest import connect, refresh_analytics
from .sync_state import cached_fingerprint, is_fresh, mark_fresh


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

    def _frame(self, league, event_kind, items):
        rows = []
        for item in items:
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
        return pd.DataFrame(rows, columns=EVENT_COLUMNS)

    def fetch(self, league, event_kind):
        endpoint = "eventspastleague.php" if event_kind == "past" else "eventsnextleague.php"
        response = self.session.get(
            f"{self.base_url}/{endpoint}",
            params={"id": THESPORTSDB_LEAGUE_IDS[league]}, timeout=(10, 45),
        )
        response.raise_for_status()
        frame = self._frame(league, event_kind, response.json().get("events") or [])
        time.sleep(2.1)
        return frame

    def fetch_season(self, competition, season):
        response = self.session.get(
            f"{self.base_url}/eventsseason.php",
            params={
                "id": THESPORTSDB_LEAGUE_IDS[competition],
                "s": str(season) if competition in CALENDAR_YEAR_TOURNAMENTS else f"{season}-{season + 1}",
            },
            timeout=(10, 45),
        )
        response.raise_for_status()
        frame = self._frame(competition, "season", response.json().get("events") or [])
        time.sleep(2.1)
        return frame


def sync_cup_events(db=DB, season=None, competitions=None, adapter=None, refresh=False):
    """Cache the free current-season window for supported cups and tournaments."""
    season = current_season() if season is None else season
    competitions = competitions or [
        code for code in TOURNAMENTS if code in THESPORTSDB_LEAGUE_IDS
    ]
    adapter = adapter or TheSportsDBRecentEvents()
    report = []
    with connect(db) as con:
        for competition in competitions:
            key = f"cup-events:{competition}:{season}"
            if not refresh and is_fresh(con, key, timedelta(hours=6)):
                report.append({"competition": competition, "season": season, "status": "cached"})
                print(report[-1], flush=True)
                continue
            try:
                frame = adapter.fetch_season(competition, season)
                if frame.empty:
                    mark_fresh(con, key)
                    report.append({
                        "competition": competition, "season": season,
                        "status": "unavailable", "rows": 0,
                    })
                    print(report[-1], flush=True)
                    continue
                con.register("incoming_cup_events", frame[EVENT_COLUMNS])
                completed = frame[frame.home_goals.notna() & frame.away_goals.notna()].copy()
                if not completed.empty:
                    tournament = pd.DataFrame({
                        "competition": completed.league,
                        "season": completed.season.astype(int),
                        "stage": completed.status.replace("", "Cup match"),
                        "group_name": "",
                        "match_date": completed.match_date,
                        "home_team": completed.home_team,
                        "away_team": completed.away_team,
                        "home_goals": completed.home_goals.astype(int),
                        "away_goals": completed.away_goals.astype(int),
                        "home_penalties": None,
                        "away_penalties": None,
                        "venue": completed.venue.fillna(""),
                        "neutral": False,
                        "status": completed.status.replace("", "FINISHED"),
                        "source": SOURCE_EVENTS,
                        "source_url": completed.event_id.map(
                            lambda event_id: f"https://www.thesportsdb.com/event/{event_id}"
                        ),
                        "fetched_at": datetime.now(),
                    })
                    con.register("incoming_cup_matches", tournament)
                con.execute("BEGIN")
                try:
                    con.execute(
                        "DELETE FROM recent_events WHERE source=? AND league=? AND season=? AND event_kind='season'",
                        [SOURCE_EVENTS, competition, season],
                    )
                    con.execute(
                        f"INSERT INTO recent_events ({', '.join(EVENT_COLUMNS)}) "
                        f"SELECT {', '.join(EVENT_COLUMNS)} FROM incoming_cup_events"
                    )
                    if not completed.empty:
                        con.execute(
                            "DELETE FROM tournament_matches WHERE "
                            "(competition, season, match_date, home_team, away_team) IN "
                            "(SELECT competition, season, match_date, home_team, away_team FROM incoming_cup_matches)",
                        )
                        con.execute("INSERT INTO tournament_matches SELECT * FROM incoming_cup_matches")
                    mark_fresh(con, key)
                    con.execute("COMMIT")
                except Exception:
                    con.execute("ROLLBACK")
                    raise
                finally:
                    con.unregister("incoming_cup_events")
                    if not completed.empty:
                        con.unregister("incoming_cup_matches")
                report.append({"competition": competition, "season": season, "status": "success", "rows": len(frame)})
            except Exception as exc:
                report.append({"competition": competition, "season": season, "status": "failed", "detail": str(exc)})
            print(report[-1], flush=True)
    return report


def _season_not_started(exc, today=None):
    """Football-Data publishes a season's CSV with its first results (August). Between the
    1 July rollover and kickoff the file is missing or empty: expected, not a failure."""
    if (today or date.today()).month not in (7, 8, 9):
        return False
    missing = getattr(getattr(exc, "response", None), "status_code", None) == 404
    return missing or "No completed matches" in str(exc)


def sync_recent(db=DB, year=None, leagues=None, refresh=False, event_adapter=None):
    year = year if year is not None else current_season()
    leagues = leagues if leagues is not None else list(RECENT_LEAGUES)
    match_adapter = FootballDataCSV(
        DATA / "raw", refresh=refresh, require_complete=False, max_age=timedelta(hours=6),
    )
    event_adapter = event_adapter or TheSportsDBRecentEvents()
    report = []
    matches_changed = False
    with connect(db) as con:
        for league in leagues:
            try:
                batch = match_adapter.fetch(league, year)
                frame = batch.frame.copy()
                key = f"recent-matches:{league}:{year}"
                existing_count = con.execute(
                    "SELECT count(*) FROM recent_matches WHERE league=? AND season=?", [league, year]
                ).fetchone()[0]
                if cached_fingerprint(con, key) == batch.digest and existing_count == len(frame):
                    mark_fresh(con, key, batch.digest)  # record the successful check, not only changes
                    report.append({"league": league, "season": year, "source": SOURCE_CSV, "status": "cached", "rows": len(frame)})
                    print(report[-1], flush=True)
                    continue
                frame["source"] = SOURCE_CSV
                frame["fetched_at"] = datetime.now()
                con.register("incoming_recent", frame)
                con.execute("BEGIN")
                try:
                    # Replace this source's partition and any provisional rows it now covers.
                    con.execute(
                        "DELETE FROM recent_matches r WHERE league=? AND season=? AND (source=? OR EXISTS ("
                        "SELECT 1 FROM incoming_recent i WHERE i.home_team=r.home_team AND i.away_team=r.away_team))",
                        [league, year, SOURCE_CSV],
                    )
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
                    mark_fresh(con, key, batch.digest)
                    con.execute("COMMIT")
                except Exception:
                    con.execute("ROLLBACK")
                    raise
                finally:
                    con.unregister("incoming_recent")
                report.append({"league": league, "season": year, "source": SOURCE_CSV, "status": "success", "rows": len(frame)})
                matches_changed = True
            except Exception as exc:
                status = "pending" if _season_not_started(exc) else "failed"
                report.append({"league": league, "season": year, "source": SOURCE_CSV, "status": status, "detail": str(exc)})
            print(report[-1], flush=True)

        for league in leagues:
            for event_kind in ("past", "next"):
                key = f"recent-events:{league}:{event_kind}"
                if not refresh and is_fresh(con, key, timedelta(hours=1)):
                    report.append({"league": league, "event_kind": event_kind, "source": SOURCE_EVENTS, "status": "cached"})
                    continue
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
                            mark_fresh(con, key)
                            con.execute("COMMIT")
                        except Exception:
                            con.execute("ROLLBACK")
                            raise
                        finally:
                            con.unregister("incoming_events")
                    else:
                        mark_fresh(con, key)
                    report.append({"league": league, "event_kind": event_kind, "source": SOURCE_EVENTS, "status": "success", "rows": len(frame)})
                except Exception as exc:
                    report.append({"league": league, "event_kind": event_kind, "source": SOURCE_EVENTS, "status": "failed", "detail": str(exc)})
                    print(report[-1], flush=True)
        if matches_changed:
            refresh_analytics(con)
    return report


def main():
    parser = argparse.ArgumentParser(description="Sync current-season matches from free sources")
    parser.add_argument("--season", type=int)
    parser.add_argument("--leagues", nargs="+", choices=RECENT_LEAGUES)
    parser.add_argument("--cached", action="store_true", help="Use cached CSVs instead of redownloading")
    parser.add_argument("--refresh", action="store_true", help="Bypass local freshness checks")
    args = parser.parse_args()
    if args.cached and args.refresh:
        parser.error("--cached and --refresh cannot be combined")
    result = sync_recent(year=args.season, leagues=args.leagues, refresh=args.refresh)
    raise SystemExit(1 if any(row["status"] == "failed" and row["source"] == SOURCE_CSV for row in result) else 0)


if __name__ == "__main__":
    main()
