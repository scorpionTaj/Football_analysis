"""Guarded weekly fixture import from Football-Data.co.uk's public CSV."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from hashlib import sha256
from io import BytesIO
from pathlib import Path
import re

import pandas as pd
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from .config import DATA, DB, RECENT_LEAGUES
from .ingest import connect
from .recent import EVENT_COLUMNS
from .sync_state import is_fresh, mark_fresh
from .teams import team_key


FIXTURES_URL = "https://www.football-data.co.uk/fixtures.csv"
SOURCE = "Football-Data.co.uk fixtures"


def normalize_fixtures(raw: bytes, season: int, leagues: list[str], today: date | None = None) -> pd.DataFrame:
    """Keep only dated, future fixtures; never mistake an HTML error for CSV."""
    today = today or date.today()
    frame = pd.read_csv(BytesIO(raw), encoding="utf-8-sig", on_bad_lines="error")
    required = {"Div", "Date", "HomeTeam", "AwayTeam"}
    if not required.issubset(frame):
        raise ValueError(f"Fixture CSV is missing {sorted(required - set(frame))}")
    frame = frame.dropna(subset=list(required)).copy()
    frame = frame[frame.Div.isin(leagues)].copy()
    frame["match_date"] = pd.to_datetime(frame.Date, dayfirst=True, format="mixed", errors="coerce").dt.date
    frame = frame[frame.match_date.notna()].copy()
    frame = frame[frame.match_date.between(max(today, date(season, 7, 1)), date(season + 1, 6, 30))]
    frame["HomeTeam"] = frame.HomeTeam.astype(str).str.strip()
    frame["AwayTeam"] = frame.AwayTeam.astype(str).str.strip()
    frame = frame[(frame.HomeTeam != "") & (frame.AwayTeam != "")]
    frame = frame[frame.HomeTeam.map(team_key) != frame.AwayTeam.map(team_key)]
    if "Time" not in frame:
        frame["Time"] = None
    frame["Time"] = frame.Time.map(
        lambda value: str(value).strip() if pd.notna(value) and re.fullmatch(r"\d{1,2}:\d{2}", str(value).strip()) else None
    )
    frame = frame.drop_duplicates(["Div", "match_date", "HomeTeam", "AwayTeam"])
    return frame[["Div", "match_date", "Time", "HomeTeam", "AwayTeam"]].reset_index(drop=True)


class FootballDataFixtures:
    def __init__(self, cache: Path = DATA / "raw" / "fixtures.csv", refresh: bool = False):
        self.cache = Path(cache)
        self.refresh = refresh
        self.session = requests.Session()
        self.session.headers["User-Agent"] = "football-analysis/0.9 (personal research; cached fixtures)"
        retry = Retry(total=3, backoff_factor=1, status_forcelist=[429, 500, 502, 503, 504], respect_retry_after_header=True)
        self.session.mount("https://", HTTPAdapter(max_retries=retry))

    def fetch(self) -> bytes:
        if self.cache.exists() and not self.refresh and datetime.fromtimestamp(self.cache.stat().st_mtime) >= datetime.now() - timedelta(hours=6):
            return self.cache.read_bytes()
        response = self.session.get(FIXTURES_URL, timeout=(10, 45))
        response.raise_for_status()
        raw = response.content
        # Validate before replacing a known-good local download.
        columns = set(pd.read_csv(BytesIO(raw), nrows=0).columns)
        if not {"Div", "Date", "HomeTeam", "AwayTeam"}.issubset(columns):
            raise ValueError("Downloaded fixture response is not the expected CSV")
        self.cache.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.cache.with_suffix(f"{self.cache.suffix}.tmp")
        temporary.write_bytes(raw)
        temporary.replace(self.cache)
        return raw


def sync_fixtures(db: Path = DB, season: int | None = None, leagues: list[str] | None = None,
                  refresh: bool = False, adapter: FootballDataFixtures | None = None,
                  today: date | None = None) -> dict:
    today = today or date.today()
    season = season if season is not None else (today.year if today.month >= 7 else today.year - 1)
    leagues = leagues if leagues is not None else list(RECENT_LEAGUES)
    adapter = adapter or FootballDataFixtures(refresh=refresh)
    key = f"weekly-fixtures:{season}:{','.join(sorted(leagues))}"
    with connect(db) as con:
        if not refresh and is_fresh(con, key, timedelta(hours=6)):
            return {"status": "cached"}
        try:
            raw = adapter.fetch()
            frame = normalize_fixtures(raw, season, leagues, today)
            if frame.empty:
                return {"status": "unavailable", "detail": "The published weekly CSV has no future fixtures in scope."}
            digest = sha256(raw).hexdigest()
            # Reconcile to clubs already observed in this season. An uncertain
            # provider name is omitted rather than creating a duplicate club.
            teams = con.execute(
                "SELECT league, home_team FROM recent_matches WHERE season=? "
                "UNION SELECT league, away_team FROM recent_matches WHERE season=?",
                [season, season],
            ).fetchall()
            known = {(league, team_key(name)): name for league, name in teams}
            rows = []
            now = datetime.now()
            for row in frame.itertuples(index=False):
                home = known.get((row.Div, team_key(row.HomeTeam)))
                away = known.get((row.Div, team_key(row.AwayTeam)))
                if not home or not away:
                    continue
                identity = f"{row.Div}:{season}:{row.match_date}:{team_key(home)}:{team_key(away)}"
                rows.append({
                    "event_id": f"fd-fixture-{sha256(identity.encode()).hexdigest()[:20]}",
                    "league": row.Div, "season": season, "match_date": row.match_date,
                    "home_team": home, "away_team": away,
                    "home_goals": None, "away_goals": None, "status": "Scheduled",
                    "event_kind": "fixture", "source": SOURCE, "fetched_at": now,
                    "kickoff_time": row.Time, "venue": None, "home_coach": None,
                    "away_coach": None, "home_formation": None, "away_formation": None,
                    "referee": None, "attendance": None,
                })
            incoming = pd.DataFrame(rows, columns=EVENT_COLUMNS)
            if not rows:
                return {"status": "unavailable", "detail": "Future fixtures could not be reconciled to current clubs."}
            con.register("incoming_fixtures", incoming)
            con.execute("BEGIN")
            try:
                placeholders = ",".join("?" for _ in leagues)
                con.execute(
                    f"DELETE FROM recent_events WHERE source=? AND season=? AND league IN ({placeholders})",
                    [SOURCE, season, *leagues],
                )
                if rows:
                    con.execute(
                        f"INSERT INTO recent_events ({', '.join(EVENT_COLUMNS)}) "
                        f"SELECT {', '.join(EVENT_COLUMNS)} FROM incoming_fixtures"
                    )
                mark_fresh(con, key, digest)
                con.execute("COMMIT")
            except Exception:
                con.execute("ROLLBACK")
                raise
            finally:
                con.unregister("incoming_fixtures")
            return {"status": "success", "rows": len(rows), "unmapped": len(frame) - len(rows)}
        except (requests.RequestException, ValueError, UnicodeError, OSError, pd.errors.ParserError) as exc:
            return {"status": "unavailable", "detail": str(exc)}
