"""Cache club and competition artwork from TheSportsDB's documented free API."""

import argparse
from datetime import datetime

import pandas as pd

from .config import CLUBS, DB, RECENT_LEAGUES, THESPORTSDB_LEAGUE_IDS
from .ingest import connect
from .players import SOURCE, TheSportsDBPlayers


class TheSportsDBMedia(TheSportsDBPlayers):
    def league(self, league_id):
        rows = self._get("lookupleague.php", {"id": league_id}, "leagues")
        return (rows or [None])[0]


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


def sync_media(db=DB, clubs=None, leagues=None, adapter=None):
    clubs = clubs if clubs is not None else list(CLUBS.values())
    leagues = leagues if leagues is not None else list(RECENT_LEAGUES)
    adapter = adapter or TheSportsDBMedia()
    report = []
    team_rows = []
    league_rows = []

    for club in clubs:
        try:
            provider = adapter.find_team(club)
            if not provider:
                raise ValueError("Team was not found")
            team_rows.append({"team": club, "provider": provider})
            report.append({"kind": "team", "name": club, "status": "success"})
        except Exception as exc:
            report.append({"kind": "team", "name": club, "status": "failed", "detail": str(exc)})
        print(report[-1], flush=True)

    for league_code in leagues:
        try:
            provider = adapter.league(THESPORTSDB_LEAGUE_IDS[league_code])
            if not provider:
                raise ValueError("Competition was not found")
            league_rows.append({
                "league_code": league_code,
                "league": RECENT_LEAGUES[league_code],
                "provider": provider,
            })
            report.append({"kind": "competition", "name": RECENT_LEAGUES[league_code], "status": "success"})
        except Exception as exc:
            report.append({
                "kind": "competition", "name": RECENT_LEAGUES.get(league_code, league_code),
                "status": "failed", "detail": str(exc),
            })
        print(report[-1], flush=True)

    teams = _team_media_frame(team_rows)
    competitions = _competition_media_frame(league_rows)
    with connect(db) as con:
        con.execute("BEGIN")
        try:
            if clubs:
                placeholders = ",".join("?" for _ in clubs)
                con.execute(
                    f"DELETE FROM team_media WHERE source=? AND team IN ({placeholders})",
                    [SOURCE, *clubs],
                )
            if not teams.empty:
                con.register("incoming_team_media", teams)
                con.execute("INSERT INTO team_media SELECT * FROM incoming_team_media")
            if leagues:
                placeholders = ",".join("?" for _ in leagues)
                con.execute(
                    f"DELETE FROM competition_media WHERE source=? AND league_code IN ({placeholders})",
                    [SOURCE, *leagues],
                )
            if not competitions.empty:
                con.register("incoming_competition_media", competitions)
                con.execute("INSERT INTO competition_media SELECT * FROM incoming_competition_media")
            con.execute("COMMIT")
        except Exception:
            con.execute("ROLLBACK")
            raise
        finally:
            if not teams.empty:
                con.unregister("incoming_team_media")
            if not competitions.empty:
                con.unregister("incoming_competition_media")
    return report


def main():
    parser = argparse.ArgumentParser(description="Sync free club and competition artwork")
    parser.add_argument("--clubs", nargs="+")
    parser.add_argument("--leagues", nargs="+")
    args = parser.parse_args()
    result = sync_media(clubs=args.clubs, leagues=args.leagues)
    raise SystemExit(1 if any(row["status"] == "failed" for row in result) else 0)


if __name__ == "__main__":
    main()
