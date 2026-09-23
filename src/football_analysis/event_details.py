"""Capped TheSportsDB event-detail adapter for cached recent fixtures."""

from __future__ import annotations

import argparse
import time
from datetime import datetime, timedelta

import pandas as pd
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from .config import DB
from .ingest import connect
from .sync_state import is_fresh, mark_fresh

SOURCE = "TheSportsDB"


class TheSportsDBEventDetails:
    """Return the three useful free event-detail collections behind one interface."""

    base_url = "https://www.thesportsdb.com/api/v1/json/123"

    def __init__(self, interval=2.1, session=None):
        self.interval = interval
        self.session = session or requests.Session()
        self.session.headers["User-Agent"] = "football-analysis/0.8 (personal analytics)"
        retry = Retry(
            total=3, backoff_factor=1, status_forcelist=[429, 500, 502, 503, 504],
            respect_retry_after_header=True,
        )
        self.session.mount("https://", HTTPAdapter(max_retries=retry))

    def _get(self, endpoint, event_id, key):
        response = self.session.get(
            f"{self.base_url}/{endpoint}", params={"id": event_id}, timeout=(10, 45),
        )
        response.raise_for_status()
        rows = response.json().get(key) or []
        time.sleep(self.interval)
        return rows

    def fetch(self, event_id):
        return {
            "statistics": self._get("lookupeventstats.php", event_id, "eventstats"),
            "timeline": self._get("lookuptimeline.php", event_id, "timeline"),
            "lineups": self._get("lookuplineup.php", event_id, "lineup"),
        }


def detail_frames(event_id, payload):
    now = datetime.now()
    statistics = pd.DataFrame([{
        "source": SOURCE, "event_id": str(event_id),
        "statistic": row.get("strStat") or "Unknown",
        "home_value": pd.to_numeric(row.get("intHome"), errors="coerce"),
        "away_value": pd.to_numeric(row.get("intAway"), errors="coerce"),
        "fetched_at": now,
    } for row in payload.get("statistics", [])])
    timeline = pd.DataFrame([{
        "source": SOURCE, "timeline_id": str(row.get("idTimeline") or f"{event_id}-{index}"),
        "event_id": str(event_id), "minute": str(row.get("intTime") or ""),
        "event_type": row.get("strTimeline") or "", "detail": row.get("strTimelineDetail") or "",
        "team": row.get("strTeam") or "", "player_id": str(row.get("idPlayer") or ""),
        "player": row.get("strPlayer") or "", "assist": row.get("strAssist") or "",
        "is_home": (row.get("strHome") or "").casefold() == "yes",
        "comment": "" if row.get("strComment") in (None, "NULL") else row.get("strComment"),
        "fetched_at": now,
    } for index, row in enumerate(payload.get("timeline", []))])
    lineups = pd.DataFrame([{
        "source": SOURCE, "lineup_id": str(row.get("idLineup") or f"{event_id}-{index}"),
        "event_id": str(event_id), "team": row.get("strTeam") or "",
        "player_id": str(row.get("idPlayer") or ""), "player": row.get("strPlayer") or "",
        "position": row.get("strPosition") or "",
        "is_home": (row.get("strHome") or "").casefold() == "yes",
        "is_substitute": (row.get("strSubstitute") or "").casefold() == "yes",
        "shirt_number": str(row.get("intSquadNumber") or ""),
        "cutout_url": row.get("strCutout") or "", "fetched_at": now,
    } for index, row in enumerate(payload.get("lineups", []))])
    return statistics, timeline, lineups


def sync_event_details(db=DB, event_ids=None, adapter=None, refresh=False, leagues=None):
    adapter = adapter or TheSportsDBEventDetails()
    report = []
    with connect(db) as con:
        if event_ids is None:
            condition = ""
            params = []
            if leagues is not None:
                if not leagues:
                    event_ids = []
                else:
                    condition = f"AND league IN ({','.join('?' for _ in leagues)})"
                    params = list(leagues)
            if event_ids is None:
                event_ids = [row[0] for row in con.execute(f"""
                SELECT event_id FROM (
                    SELECT event_id, row_number() OVER (
                        PARTITION BY league ORDER BY match_date DESC, fetched_at DESC
                    ) AS priority
                    FROM recent_events WHERE event_kind IN ('past', 'season') {condition}
                ) WHERE priority=1
                """, params).fetchall()]
        for event_id in event_ids:
            key = f"event-details:{event_id}"
            if not refresh and is_fresh(con, key, timedelta(days=1)):
                report.append({"event_id": str(event_id), "status": "cached"})
                print(report[-1], flush=True)
                continue
            try:
                frames = detail_frames(event_id, adapter.fetch(event_id))
                names = ("event_statistics", "event_timeline", "event_lineups")
                con.execute("BEGIN")
                try:
                    for table, frame in zip(names, frames):
                        con.execute(f"DELETE FROM {table} WHERE source=? AND event_id=?", [SOURCE, str(event_id)])
                        if not frame.empty:
                            incoming = f"incoming_{table}"
                            con.register(incoming, frame)
                            con.execute(f"INSERT INTO {table} SELECT * FROM {incoming}")
                            con.unregister(incoming)
                    mark_fresh(con, key)
                    con.execute("COMMIT")
                except Exception:
                    con.execute("ROLLBACK")
                    raise
                counts = dict(zip(("statistics", "timeline", "lineups"), map(len, frames)))
                report.append({"event_id": str(event_id), "status": "success", **counts})
            except Exception as exc:
                report.append({"event_id": str(event_id), "status": "failed", "detail": str(exc)})
            print(report[-1], flush=True)
    return report


def main():
    parser = argparse.ArgumentParser(description="Sync capped free match statistics, timeline and lineups")
    parser.add_argument("--event-ids", nargs="+")
    parser.add_argument("--leagues", nargs="+", help="Limit automatic event selection to competition codes")
    parser.add_argument("--refresh", action="store_true", help="Bypass persisted freshness checks")
    args = parser.parse_args()
    report = sync_event_details(event_ids=args.event_ids, leagues=args.leagues, refresh=args.refresh)
    raise SystemExit(1 if any(row["status"] == "failed" for row in report) else 0)


if __name__ == "__main__":
    main()
