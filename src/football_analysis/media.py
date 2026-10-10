"""Cache club and competition artwork from TheSportsDB's documented free API."""

import argparse
from datetime import datetime, timedelta

import pandas as pd

from .config import CLUBS, COMPETITIONS, DB, THESPORTSDB_BADGE_IDS, current_season
from .ingest import connect
from .players import SOURCE, TheSportsDBPlayers
from .teams import display_team, team_key


class TheSportsDBMedia(TheSportsDBPlayers):
    def league(self, league_id):
        rows = self._get("lookupleague.php", {"id": league_id}, "leagues")
        return (rows or [None])[0]


def discover_missing_clubs(db=DB, retry_missing=False):
    """Return uncached clubs and nations, prioritizing the current season."""
    with connect(db) as con:
        names = con.sql("""
            SELECT team FROM team_seasons
            UNION SELECT home_team FROM recent_matches
            UNION SELECT away_team FROM recent_matches
            UNION SELECT home_team FROM tournament_matches
            UNION SELECT away_team FROM tournament_matches
        """).df()["team"].dropna().tolist()
        existing = con.sql("SELECT team FROM team_media").df()["team"].dropna().tolist()
        missing = con.sql(
            "SELECT team_key FROM media_lookup_cache WHERE status='not_found' AND checked_at >= ?",
            params=[datetime.now() - timedelta(days=30)],
        ).df()["team_key"].tolist() if not retry_missing else []
        active = con.sql(
            "SELECT home_team AS team FROM recent_matches WHERE season=? "
            "UNION SELECT away_team FROM recent_matches WHERE season=?",
            params=[current_season(), current_season()],
        ).df()["team"].dropna().tolist()
    existing_keys = {team_key(name) for name in existing}
    missing_keys = set(missing)
    active_keys = {team_key(name) for name in active}
    candidates: dict[str, list[str]] = {}
    for name in names:
        key = team_key(name)
        if key and key not in existing_keys and key not in missing_keys:
            candidates.setdefault(key, []).append(display_team(name))
    representatives = [
        min(values, key=lambda value: ("(" in value, len(value), value.casefold()))
        for values in candidates.values()
    ]
    return sorted(representatives, key=lambda name: (team_key(name) not in active_keys, name.casefold()))


def _team_media_frame(rows):
    now = datetime.now()
    return pd.DataFrame([
        {
            "source": SOURCE,
            "team_id": row["provider"]["idTeam"],
            "team": row["team"],
            "badge_url": row["provider"].get("strBadge") or "",
            "logo_url": row["provider"].get("strLogo") or "",
            "banner_url": row["provider"].get("strBanner") or "",
            "fanart_url": row["provider"].get("strFanart1") or "",
            "stadium_url": row["provider"].get("strStadiumThumb") or "",
            "fetched_at": now,
        }
        for row in rows
    ])


def _competition_media_frame(rows):
    now = datetime.now()
    return pd.DataFrame([
        {
            "source": SOURCE,
            "league_code": row["league_code"],
            "league_id": str(row["provider"]["idLeague"]),
            "league": row["league"],
            "badge_url": row["provider"].get("strBadge") or "",
            "logo_url": row["provider"].get("strLogo") or "",
            "banner_url": row["provider"].get("strBanner") or "",
            "trophy_url": row["provider"].get("strTrophy") or "",
            "fanart_url": row["provider"].get("strFanart1") or "",
            "fetched_at": now,
        }
        for row in rows
    ])


def _save_media_batch(db, teams, missing, leagues):
    """Publish each small batch so an interrupted backfill can resume."""
    if not teams and not missing and not leagues:
        return
    team_frame = _team_media_frame(teams)
    league_frame = _competition_media_frame(leagues)
    with connect(db) as con:
        con.execute("BEGIN")
        try:
            for row in teams:
                con.execute("DELETE FROM team_media WHERE source=? AND team=?", [SOURCE, row["team"]])
                con.execute("DELETE FROM media_lookup_cache WHERE team_key=?", [team_key(row["team"])])
            if not team_frame.empty:
                con.register("incoming_team_media", team_frame)
                con.execute("INSERT INTO team_media SELECT * FROM incoming_team_media")
            for name in missing:
                key = team_key(name)
                con.execute("DELETE FROM media_lookup_cache WHERE team_key=?", [key])
                con.execute(
                    "INSERT INTO media_lookup_cache VALUES (?, ?, 'not_found', ?)",
                    [key, name, datetime.now()],
                )
            for row in leagues:
                con.execute("DELETE FROM competition_media WHERE source=? AND league_code=?", [SOURCE, row["league_code"]])
            if not league_frame.empty:
                con.register("incoming_competition_media", league_frame)
                con.execute("INSERT INTO competition_media SELECT * FROM incoming_competition_media")
            con.execute("COMMIT")
        except Exception:
            con.execute("ROLLBACK")
            raise
        finally:
            if not team_frame.empty:
                con.unregister("incoming_team_media")
            if not league_frame.empty:
                con.unregister("incoming_competition_media")


def sync_media(db=DB, clubs=None, leagues=None, adapter=None, *, refresh=False, retry_missing=False, batch_size=10):
    clubs = clubs if clubs is not None else list(CLUBS.values())
    leagues = leagues if leagues is not None else list(THESPORTSDB_BADGE_IDS)
    adapter = adapter or TheSportsDBMedia()
    if batch_size < 1:
        raise ValueError("batch_size must be positive")
    report = []
    with connect(db) as con:
        existing = {team_key(name) for (name,) in con.execute("SELECT team FROM team_media").fetchall()}
        unavailable = {
            key for (key,) in con.execute(
                "SELECT team_key FROM media_lookup_cache WHERE status='not_found' AND checked_at >= ?",
                [datetime.now() - timedelta(days=30)],
            ).fetchall()
        }
        existing_leagues = {code for (code,) in con.execute("SELECT league_code FROM competition_media").fetchall()}
    pending_clubs = []
    seen = set()
    for club in clubs:
        key = team_key(club)
        if not key or key in seen:
            continue
        seen.add(key)
        if not refresh and key in existing:
            report.append({"kind": "team", "name": club, "status": "cached"})
        elif not refresh and not retry_missing and key in unavailable:
            report.append({"kind": "team", "name": club, "status": "cached_missing"})
        else:
            pending_clubs.append(club)
    pending_leagues = [code for code in dict.fromkeys(leagues) if refresh or code not in existing_leagues]
    interval = getattr(adapter, "interval", None)
    plan = {"kind": "media_plan", "teams_to_check": len(pending_clubs),
            "teams_cached": len(clubs) - len(pending_clubs),
            "competitions_to_check": len(pending_leagues)}
    if isinstance(interval, (int, float)):
        plan["minimum_minutes"] = round((len(pending_clubs) + len(pending_leagues)) * interval / 60, 1)
    print(plan, flush=True)

    team_rows = []
    missing_rows = []
    consecutive_errors = 0
    for index, club in enumerate(pending_clubs, 1):
        try:
            provider = adapter.find_team(club)
            if not provider:
                missing_rows.append(club)
                report.append({"kind": "team", "name": club, "status": "not_found"})
            else:
                team_rows.append({"team": club, "provider": provider})
                report.append({"kind": "team", "name": club, "status": "success"})
            consecutive_errors = 0
        except KeyboardInterrupt:
            _save_media_batch(db, team_rows, missing_rows, [])
            print({"kind": "media_paused", "saved_pending": len(team_rows) + len(missing_rows)}, flush=True)
            raise
        except Exception as exc:
            report.append({"kind": "team", "name": club, "status": "failed", "detail": str(exc)})
            consecutive_errors += 1
        if index % batch_size == 0 or index == len(pending_clubs) or consecutive_errors >= 3:
            _save_media_batch(db, team_rows, missing_rows, [])
            print({"kind": "media_progress", "checked": index, "total": len(pending_clubs),
                   "saved": len(team_rows), "not_found": len(missing_rows),
                   "last_team": club, "last_status": report[-1]["status"]}, flush=True)
            team_rows, missing_rows = [], []
        if consecutive_errors >= 3:
            raise RuntimeError("Artwork provider failed three requests in a row; saved batches can be resumed")

    league_rows = []
    for league_code in pending_leagues:
        try:
            provider = adapter.league(THESPORTSDB_BADGE_IDS[league_code])
            if not provider:
                report.append({"kind": "competition", "name": COMPETITIONS[league_code], "status": "not_found"})
                continue
            league_rows.append({
                "league_code": league_code,
                "league": COMPETITIONS[league_code],
                "provider": provider,
            })
            report.append({"kind": "competition", "name": COMPETITIONS[league_code], "status": "success"})
        except Exception as exc:
            report.append({
                "kind": "competition", "name": COMPETITIONS.get(league_code, league_code),
                "status": "failed", "detail": str(exc),
            })
        print(report[-1], flush=True)
    _save_media_batch(db, [], [], league_rows)
    return report


def main():
    parser = argparse.ArgumentParser(description="Sync free club and competition artwork")
    parser.add_argument("--clubs", nargs="+")
    parser.add_argument("--leagues", nargs="+")
    parser.add_argument("--all-teams", action="store_true", help="Sync missing media for every loaded club and nation")
    parser.add_argument("--max-teams", type=int, help="Check at most this many missing teams in this run")
    parser.add_argument("--refresh", action="store_true", help="Recheck cached artwork")
    parser.add_argument("--retry-missing", action="store_true", help="Retry teams that were not found within the last 30 days")
    args = parser.parse_args()
    clubs = discover_missing_clubs(retry_missing=args.retry_missing) if args.all_teams else args.clubs
    if args.max_teams is not None:
        if args.max_teams < 1:
            parser.error("--max-teams must be positive")
        clubs = (clubs if clubs is not None else list(CLUBS.values()))[:args.max_teams]
    leagues = [] if args.all_teams and args.leagues is None else args.leagues
    result = sync_media(clubs=clubs, leagues=leagues, refresh=args.refresh, retry_missing=args.retry_missing)
    raise SystemExit(1 if any(row["status"] == "failed" for row in result) else 0)


if __name__ == "__main__":
    main()
