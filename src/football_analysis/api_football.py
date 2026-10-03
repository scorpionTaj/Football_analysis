"""Current squads for the featured clubs from API-Football (https://www.api-football.com).

Silent no-op unless API_FOOTBALL_KEY is set (free plan: 100 requests/day, 10/minute). Runs only
in the full refresh, never during a page render. Each club's squad is cached for a day; the
account's remaining daily quota is read from /status (which does not count against it) and then
from each response's `x-ratelimit-requests-remaining` header, and the sync stops once it reaches
API_FOOTBALL_RESERVE (default 20) so other uses of the key keep headroom.

    uv run python -m football_analysis.api_football
"""

from __future__ import annotations

import json
import os
import time
from datetime import datetime, timedelta

import pandas as pd
import requests

from .config import CLUBS, DB
from .ingest import connect
from .sync_state import is_fresh, mark_fresh

SOURCE = "API-Football"
BASE_URL = "https://v3.football.api-sports.io"
# API-Football team ids for config.CLUBS (fixed ids, so no requests are spent on searches).
TEAM_IDS = {
    "Real Madrid": 541, "FC Barcelona": 529, "Atlético Madrid": 530, "Manchester City": 50,
    "Liverpool": 40, "Arsenal": 42, "Bayern Munich": 157, "Borussia Dortmund": 165,
    "Paris Saint-Germain": 85, "Inter Milan": 505, "AC Milan": 489, "Juventus": 496,
}
COLUMNS = ["source", "team_id", "team", "provider_team", "player_id", "player", "age", "number",
           "position", "photo_url", "source_url", "fetched_at"]


def _get(session, path, params=None):
    response = session.get(f"{BASE_URL}/{path}", params=params, timeout=(10, 30))
    response.raise_for_status()
    body = response.json()
    if body.get("errors"):  # API-Football reports key, plan and rate-limit problems with HTTP 200
        raise ValueError(f"API-Football {path}: {body['errors']}")
    return body, response


def _remaining_today(session):
    requests_ = _get(session, "status")[0]["response"]["requests"]
    return int(requests_["limit_day"]) - int(requests_["current"])


def sync_squads(db=DB, clubs=None, key=None, reserve=None, session=None,
                max_age=timedelta(hours=24), pause=6.5):
    key = key if key is not None else os.environ.get("API_FOOTBALL_KEY", "")
    if not key:
        return {"status": "skipped", "detail": "API_FOOTBALL_KEY is not set"}
    reserve = int(os.environ.get("API_FOOTBALL_RESERVE", 20)) if reserve is None else reserve
    clubs = clubs or list(CLUBS.values())
    if session is None:
        session = requests.Session()
        session.headers.update({"x-apisports-key": key, "User-Agent": "football-analysis/0.9 (daily squad cache)"})
    report = {"status": "success", "updated": [], "cached": 0, "skipped_for_quota": []}
    with connect(db) as con:
        due = [club for club in clubs if not is_fresh(con, f"api-football-squad:{TEAM_IDS[club]}", max_age)]
        report["cached"] = len(clubs) - len(due)
        if not due:
            return {**report, "status": "cached"}
        remaining = _remaining_today(session)
        for index, club in enumerate(due):
            if remaining <= reserve:
                report["skipped_for_quota"] = due[index:]
                break
            if index:
                time.sleep(pause)  # free plan: 10 requests per minute
            team_id = TEAM_IDS[club]
            body, response = _get(session, "players/squads", {"team": team_id})
            header = response.headers.get("x-ratelimit-requests-remaining")
            remaining = int(header) if header is not None else remaining - 1
            now = datetime.now()
            frame = pd.DataFrame([{
                "source": SOURCE, "team_id": team_id, "team": club, "provider_team": entry["team"]["name"],
                "player_id": int(player["id"]), "player": player["name"], "age": player.get("age"),
                "number": player.get("number"), "position": player.get("position"),
                "photo_url": player.get("photo"), "source_url": response.url, "fetched_at": now,
            } for entry in body.get("response", []) for player in entry.get("players", [])], columns=COLUMNS)
            if frame.empty:
                raise ValueError(f"API-Football returned no squad for {club} ({team_id})")
            con.register("incoming_squad", frame)
            con.execute("BEGIN")
            try:
                con.execute("DELETE FROM api_football_squads WHERE team_id = ?", [team_id])
                con.execute(f"INSERT INTO api_football_squads ({', '.join(COLUMNS)}) "
                            f"SELECT {', '.join(COLUMNS)} FROM incoming_squad")
                mark_fresh(con, f"api-football-squad:{team_id}", str(len(frame)))
                con.execute("COMMIT")
            except Exception:
                con.execute("ROLLBACK")
                raise
            finally:
                con.unregister("incoming_squad")
            report["updated"].append({"club": club, "players": len(frame)})
        report["remaining_today"] = remaining
    if report["skipped_for_quota"]:
        report["status"] = "partial"
        report["detail"] = (f"Stopped at the {reserve}-request reserve; {len(report['skipped_for_quota'])} "
                            "clubs wait for tomorrow's quota")
    return report


if __name__ == "__main__":
    print(json.dumps(sync_squads(), default=str))
