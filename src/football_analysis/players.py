"""Capped player profile and statistic ingestion from TheSportsDB free v1 API."""

import argparse
import re
import time
from datetime import datetime, timedelta

import pandas as pd
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from .config import CLUBS, DB
from .ingest import connect
from .sync_state import is_fresh, mark_fresh
from .teams import team_key


SOURCE = "TheSportsDB"
TEAM_SEARCH_NAMES = {
    "AEK": "AEK Athens",
    "Bayern München": "Bayern Munich",
    "CF América": "Club America",
    "FC København": "FC Copenhagen",
    "FK Bodø/Glimt": "Bodo Glimt",
    "Dinamo Kiev": "Dynamo Kyiv",
    "Leeds": "Leeds United",
    "Kalamata": "Kalamata FC",
    "Oud-Heverlee Leuven": "OH Leuven",
    "Oviedo": "Real Oviedo",
    "PAE Olympiakos SFP": "Olympiacos",
    "Qarabağ Ağdam FK": "Qarabag",
    "Reims": "Stade de Reims",
    "Royale Union Saint-Gilloise": "Union Saint-Gilloise",
    "Sporting Clube de Braga": "Sporting Braga",
    "Valladolid": "Real Valladolid",
    "Volos NFC": "Volos",
    "Zenit St. Petersburg": "Zenit Saint Petersburg",
    "FC Barcelona": "Barcelona",
    "Paris Saint-Germain": "Paris Saint Germain",
    "Nott'm Forest": "Nottingham Forest FC",
    "M'gladbach": "Borussia Monchengladbach",
    "FC Koln": "FC Cologne",
    "Sociedad": "Real Sociedad",
    "Vallecano": "Rayo Vallecano",
    "Espanol": "Espanyol",
    "Alaves": "Deportivo Alaves",
    "La Coruna": "Deportivo La Coruna",
    "Santander": "Racing Santander",
    "Sp Braga": "Sporting Braga",
    "Sp Lisbon": "Sporting CP",
    "Guimaraes": "Vitoria Guimaraes",
    "For Sittard": "Fortuna Sittard",
    "Den Haag": "ADO Den Haag",
    "Nijmegen": "NEC Nijmegen",
    "Zwolle": "PEC Zwolle",
    "St. Gilloise": "Union Saint-Gilloise",
    "St Truiden": "Sint-Truiden",
    "Standard": "Standard Liege",
    "Waregem": "Zulte Waregem",
    "Buyuksehyr": "Istanbul Basaksehir",
    "Goztep": "Goztepe",
    "Olympiakos": "Olympiacos",
    "Levadeiakos": "Levadiakos",
}


class TheSportsDBPlayers:
    base_url = "https://www.thesportsdb.com/api/v1/json/123"

    def __init__(self, interval=2.1):
        self.interval = interval
        self.session = requests.Session()
        self.session.headers["User-Agent"] = "football-analysis/0.4 (personal analytics)"
        retry = Retry(
            total=3, backoff_factor=1, status_forcelist=[429, 500, 502, 503, 504],
            respect_retry_after_header=True,
        )
        self.session.mount("https://", HTTPAdapter(max_retries=retry))

    def _get(self, endpoint, params, key):
        response = self.session.get(
            f"{self.base_url}/{endpoint}", params=params, timeout=(10, 45),
        )
        response.raise_for_status()
        time.sleep(self.interval)
        return response.json().get(key) or []

    def find_team(self, name):
        clean_name = re.sub(r"\s+\([A-Z]{3}\)$", "", name).strip()
        search_name = TEAM_SEARCH_NAMES.get(name, TEAM_SEARCH_NAMES.get(clean_name, clean_name))
        rows = self._get("searchteams.php", {"t": search_name}, "teams")
        soccer = [row for row in rows if row.get("strSport") == "Soccer"]
        exact = [
            row for row in soccer
            if (row.get("strTeam") or "").casefold() == search_name.casefold()
        ]
        return (exact or soccer or [None])[0]

    def players(self, team_id):
        return self._get("lookup_all_players.php", {"id": team_id}, "player")

    def stats(self, player_id):
        return self._get("lookupplayerstats.php", {"id": player_id}, "playerstats")


def _profile_frame(rows, team_id, team_name):
    now = datetime.now()
    output = []
    for row in rows:
        output.append({
            "source": SOURCE, "player_id": row["idPlayer"], "team_id": team_id,
            "team": team_name, "player": row.get("strPlayer") or "Unknown",
            "position": row.get("strPosition") or "", "nationality": row.get("strNationality") or "",
            "date_born": pd.to_datetime(row.get("dateBorn"), errors="coerce"),
            "shirt_number": row.get("strNumber") or "", "status": row.get("strStatus") or "",
            "height": row.get("strHeight") or "", "weight": row.get("strWeight") or "",
            "thumb_url": row.get("strThumb") or "", "cutout_url": row.get("strCutout") or "",
            "fetched_at": now,
        })
    return pd.DataFrame(output)


def _stats_frame(rows, player_id):
    now = datetime.now()
    output = []
    for row in rows:
        value = pd.to_numeric(row.get("strValue"), errors="coerce")
        if pd.isna(value):
            continue
        output.append({
            "source": SOURCE, "player_id": player_id, "team_id": row.get("idTeam") or "",
            "team": row.get("strTeam") or "", "league": row.get("strLeague") or "",
            "season": row.get("strSeason") or "", "statistic": row.get("strStatistic") or "Unknown",
            "value": float(value), "fetched_at": now,
        })
    frame = pd.DataFrame(output)
    if not frame.empty:
        frame = frame.drop_duplicates(["source", "player_id", "league", "season", "statistic"], keep="last")
    return frame


def sync_players(db=DB, clubs=None, include_stats=True, adapter=None, refresh=False):
    clubs = clubs if clubs is not None else list(CLUBS.values())
    adapter = adapter or TheSportsDBPlayers()
    report = []
    with connect(db) as con:
        for club in clubs:
            key = f"players:{'full' if include_stats else 'profiles'}:{team_key(club)}"
            age = timedelta(days=30 if include_stats else 7)
            if not refresh and is_fresh(con, key, age):
                report.append({"club": club, "status": "cached"})
                print(report[-1], flush=True)
                continue
            try:
                team = adapter.find_team(club)
                if not team:
                    raise ValueError("Team was not found")
                team_id = team["idTeam"]
                profiles = _profile_frame(adapter.players(team_id), team_id, team.get("strTeam") or club)
                if profiles.empty:
                    raise ValueError("No player profiles were returned; existing rows were kept")
                stat_frames = []
                if include_stats:
                    for player_id in profiles.player_id if not profiles.empty else []:
                        stats = _stats_frame(adapter.stats(player_id), player_id)
                        if not stats.empty:
                            stat_frames.append(stats)
                stats = pd.concat(stat_frames, ignore_index=True) if stat_frames else pd.DataFrame()
                con.execute("BEGIN")
                try:
                    con.execute("DELETE FROM players WHERE source=? AND team_id=?", [SOURCE, team_id])
                    if not profiles.empty:
                        con.register("incoming_players", profiles)
                        con.execute("INSERT INTO players SELECT * FROM incoming_players")
                    if include_stats and not stats.empty:
                        player_ids = stats.player_id.unique().tolist()
                        con.execute(
                            f"DELETE FROM player_stats WHERE source=? AND player_id IN ({','.join('?' for _ in player_ids)})",
                            [SOURCE, *player_ids],
                        )
                    if not stats.empty:
                        con.register("incoming_player_stats", stats)
                        con.execute("INSERT INTO player_stats SELECT * FROM incoming_player_stats")
                    mark_fresh(con, key)
                    if include_stats:
                        mark_fresh(con, f"players:profiles:{team_key(club)}")
                    con.execute("COMMIT")
                except Exception:
                    con.execute("ROLLBACK")
                    raise
                finally:
                    if not profiles.empty:
                        con.unregister("incoming_players")
                    if not stats.empty:
                        con.unregister("incoming_player_stats")
                report.append({"club": club, "status": "success", "players": len(profiles), "stats": len(stats)})
            except Exception as exc:
                report.append({"club": club, "status": "failed", "detail": str(exc)})
            print(report[-1], flush=True)
    return report


def main():
    parser = argparse.ArgumentParser(description="Sync capped free player profiles and statistics")
    parser.add_argument("--clubs", nargs="+")
    parser.add_argument("--profiles-only", action="store_true")
    parser.add_argument("--refresh", action="store_true", help="Bypass persisted freshness checks")
    args = parser.parse_args()
    result = sync_players(clubs=args.clubs, include_stats=not args.profiles_only, refresh=args.refresh)
    raise SystemExit(1 if any(row["status"] == "failed" for row in result) else 0)


if __name__ == "__main__":
    main()
