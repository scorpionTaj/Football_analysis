"""Guarded full-season fixture snapshots from OpenFootball's public-domain JSON."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from hashlib import sha256
import json
from pathlib import Path
import re

import pandas as pd
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from .config import DATA, DB
from .ingest import connect
from .recent import EVENT_COLUMNS
from .sync_state import is_fresh, mark_fresh
from .teams import team_key


SOURCE = "OpenFootball fixtures (CC0)"
BASE_URL = "https://raw.githubusercontent.com/openfootball/football.json/master"
LEAGUE_FILES = {
    "E0": "en.1.json", "SP1": "es.1.json", "D1": "de.1.json",
    "I1": "it.1.json", "F1": "fr.1.json", "N1": "nl.1.json",
    "P1": "pt.1.json",
}
EIGHTEEN_TEAM_LEAGUES = {"D1", "F1", "N1", "P1"}

# Source-specific spellings are explicit: fuzzy matching would risk inserting
# a full season under the wrong club identity.
ALIASES = {
    "Brighton & Hove Albion FC": "Brighton", "Coventry City FC": "Coventry",
    "Hull City AFC": "Hull", "Ipswich Town FC": "Ipswich",
    "Leeds United FC": "Leeds", "Nottingham Forest FC": "Nott'm Forest",
    "Tottenham Hotspur FC": "Tottenham",
    "Athletic Club": "Ath Bilbao", "Club Atlético de Madrid": "Ath Madrid",
    "RC Celta de Vigo": "Celta", "RC Deportivo La Coruña": "La Coruna",
    "RCD Espanyol de Barcelona": "Espanol", "Rayo Vallecano de Madrid": "Vallecano",
    "Real Racing Club de Santander": "Santander", "Real Sociedad de Fútbol": "Sociedad",
    "1. FC Köln": "FC Koln", "1. FC Union Berlin": "Union Berlin",
    "1. FSV Mainz 05": "Mainz", "FC Bayern München": "Bayern Munich",
    "SC Paderborn 07": "Paderborn", "SV 07 Elversberg": "Elversberg",
    "AS Roma": "Roma", "Bologna FC 1909": "Bologna",
    "FC Internazionale Milano": "Inter", "Frosinone Calcio": "Frosinone",
    "SS Lazio": "Lazio", "US Sassuolo Calcio": "Sassuolo",
    "AS Monaco FC": "Monaco", "ES Troyes AC": "Troyes",
    "Lille OSC": "Lille", "Olympique Lyonnais": "Lyon",
    "Olympique de Marseille": "Marseille", "Racing Club de Lens": "Lens",
    "Stade Rennais FC 1901": "Rennes",
    "ADO Den Haag": "Den Haag", "AZ": "AZ Alkmaar",
    "FC Twente '65": "Twente", "Feyenoord Rotterdam": "Feyenoord",
    "Fortuna Sittard": "For Sittard", "NEC": "Nijmegen",
    "PEC Zwolle": "Zwolle", "PSV": "PSV Eindhoven",
    "SBV Excelsior": "Excelsior", "SC Cambuur-Leeuwarden": "Cambuur",
    "Telstar 1963": "Telstar", "Willem II Tilburg": "Willem II",
    "Académico de Viseu FC": "Academico Viseu", "CD Nacional": "Nacional",
    "CD Santa Clara": "Santa Clara", "CF Estrela da Amadora": "Estrela",
    "CS Marítimo": "Maritimo", "GD Estoril Praia": "Estoril",
    "Sport Lisboa e Benfica": "Benfica", "Sporting Clube de Portugal": "Sp Lisbon",
    "Vitória Guimarães": "Guimaraes",
}


def _provider_key(name: str) -> str:
    return team_key(ALIASES.get(name, name))


def normalize_open_schedule(raw: bytes, league: str, season: int) -> pd.DataFrame:
    """Reject incomplete or malformed calendars before any stored partition changes."""
    if league not in LEAGUE_FILES:
        raise ValueError(f"No OpenFootball schedule for {league}")
    document = json.loads(raw)
    matches = document.get("matches") if isinstance(document, dict) else None
    teams_expected = 18 if league in EIGHTEEN_TEAM_LEAGUES else 20
    matches_expected = teams_expected * (teams_expected - 1)
    if not isinstance(matches, list) or len(matches) != matches_expected:
        raise ValueError(f"Expected {matches_expected} {league} fixtures, got {len(matches) if isinstance(matches, list) else 'invalid JSON'}")
    rows = []
    pairs = set()
    teams = set()
    for match in matches:
        if not isinstance(match, dict):
            raise ValueError("Fixture row is not an object")
        home, away = match.get("team1"), match.get("team2")
        if not isinstance(home, str) or not isinstance(away, str) or not home.strip() or not away.strip():
            raise ValueError("Fixture row has a missing club")
        home_key, away_key = _provider_key(home), _provider_key(away)
        if not home_key or not away_key or home_key == away_key or (home_key, away_key) in pairs:
            raise ValueError("Fixture schedule has duplicate or invalid ordered club pairs")
        pairs.add((home_key, away_key))
        teams.update((home_key, away_key))
        try:
            match_date = date.fromisoformat(match["date"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError("Fixture row has an invalid date") from exc
        if not date(season, 7, 1) <= match_date <= date(season + 1, 6, 30):
            raise ValueError("Fixture date falls outside the requested season")
        time = match.get("time")
        time = time if isinstance(time, str) and re.fullmatch(r"\d{1,2}:\d{2}", time) else None
        score = match.get("score")
        final = score.get("ft") if isinstance(score, dict) else None
        scored = isinstance(final, list) and len(final) == 2 and all(value is not None for value in final)
        rows.append({
            "match_date": match_date, "home_team": home, "away_team": away,
            "home_key": home_key, "away_key": away_key,
            "kickoff_time": time, "scored": scored,
        })
    if len(teams) != teams_expected or len(pairs) != matches_expected:
        raise ValueError("Fixture schedule is not a complete double round robin")
    dates = [row["match_date"] for row in rows]
    if max(dates) - min(dates) < timedelta(days=120):
        raise ValueError("Fixture dates do not span a plausible season")
    return pd.DataFrame(rows)


class OpenFootballFixtures:
    def __init__(self, cache_root: Path = DATA / "raw" / "openfootball-fixtures", refresh: bool = False):
        self.cache_root = Path(cache_root)
        self.refresh = refresh
        self.session = requests.Session()
        self.session.headers["User-Agent"] = "football-analysis/0.9 (personal research; cached fixtures)"
        retry = Retry(total=3, backoff_factor=1, status_forcelist=[429, 500, 502, 503, 504], respect_retry_after_header=True)
        self.session.mount("https://", HTTPAdapter(max_retries=retry))

    def fetch(self, league: str, season: int) -> bytes:
        path = self.cache_root / f"{season}-{str(season + 1)[-2:]}" / LEAGUE_FILES[league]
        if path.exists() and not self.refresh and datetime.fromtimestamp(path.stat().st_mtime) >= datetime.now() - timedelta(hours=12):
            return path.read_bytes()
        url = f"{BASE_URL}/{season}-{str(season + 1)[-2:]}/{LEAGUE_FILES[league]}"
        response = self.session.get(url, timeout=(10, 45))
        response.raise_for_status()
        raw = response.content
        normalize_open_schedule(raw, league, season)
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(f"{path.suffix}.tmp")
        temporary.write_bytes(raw)
        temporary.replace(path)
        return raw


def _known_clubs(con, league: str, season: int) -> dict[str, str]:
    known = {}
    for statement in (
        "SELECT home_team AS team FROM recent_matches WHERE league=? AND season=? "
        "UNION SELECT away_team AS team FROM recent_matches WHERE league=? AND season=?",
        "SELECT home_team AS team FROM matches WHERE league=? AND season=? "
        "UNION SELECT away_team AS team FROM matches WHERE league=? AND season=?",
    ):
        for (name,) in con.execute(statement, [league, season, league, season]).fetchall():
            known.setdefault(team_key(name), name)
    for (name,) in con.execute(
        "SELECT team FROM reference_standings WHERE league=? AND season=?", [league, season],
    ).fetchall():
        known.setdefault(team_key(name), name)
    return known


def sync_open_fixtures(
    db: Path = DB, season: int | None = None, leagues: list[str] | None = None,
    refresh: bool = False, adapter: OpenFootballFixtures | None = None,
    today: date | None = None,
) -> list[dict]:
    """Replace each verified source partition independently; retain it on any failure."""
    today = today or date.today()
    season = season if season is not None else (today.year if today.month >= 7 else today.year - 1)
    leagues = leagues if leagues is not None else list(LEAGUE_FILES)
    adapter = adapter or OpenFootballFixtures(refresh=refresh)
    reports = []
    with connect(db) as con:
        for league in leagues:
            if league not in LEAGUE_FILES:
                reports.append({"league": league, "status": "unsupported"})
                continue
            key = f"open-fixtures:{league}:{season}"
            if not refresh and is_fresh(con, key, timedelta(hours=12)):
                reports.append({"league": league, "status": "cached"})
                continue
            try:
                raw = adapter.fetch(league, season)
                full = normalize_open_schedule(raw, league, season)
                future = full[(full.match_date >= today) & (~full.scored)].copy()
                if future.empty:
                    raise ValueError("Published schedule has no future unscored fixtures")
                known = _known_clubs(con, league, season)
                if known:
                    unknown = sorted(set(full.home_key).union(full.away_key) - set(known))
                    if unknown:
                        raise ValueError(f"Unreconciled clubs: {', '.join(unknown)}")
                else:
                    known = {row.home_key: ALIASES.get(row.home_team, row.home_team) for row in full.itertuples(index=False)}
                    known.update({row.away_key: ALIASES.get(row.away_team, row.away_team) for row in full.itertuples(index=False)})
                now = datetime.now()
                rows = []
                for row in future.itertuples(index=False):
                    home, away = known[row.home_key], known[row.away_key]
                    identity = f"{league}:{season}:{row.home_key}:{row.away_key}"
                    rows.append({
                        "event_id": f"of-fixture-{sha256(identity.encode()).hexdigest()[:20]}",
                        "league": league, "season": season, "match_date": row.match_date,
                        "home_team": home, "away_team": away,
                        "home_goals": None, "away_goals": None, "status": "Scheduled",
                        "event_kind": "fixture", "source": SOURCE, "fetched_at": now,
                        "kickoff_time": row.kickoff_time, "venue": None,
                        "home_coach": None, "away_coach": None,
                        "home_formation": None, "away_formation": None,
                        "referee": None, "attendance": None,
                    })
                incoming = pd.DataFrame(rows, columns=EVENT_COLUMNS)
                con.register("incoming_open_fixtures", incoming)
                con.execute("BEGIN")
                try:
                    con.execute("DELETE FROM recent_events WHERE source=? AND league=? AND season=?", [SOURCE, league, season])
                    con.execute(
                        f"INSERT INTO recent_events ({', '.join(EVENT_COLUMNS)}) "
                        f"SELECT {', '.join(EVENT_COLUMNS)} FROM incoming_open_fixtures"
                    )
                    mark_fresh(con, key, sha256(raw).hexdigest())
                    con.execute("COMMIT")
                except Exception:
                    con.execute("ROLLBACK")
                    raise
                finally:
                    con.unregister("incoming_open_fixtures")
                reports.append({"league": league, "status": "success", "rows": len(rows)})
            except (requests.RequestException, ValueError, UnicodeError, OSError, json.JSONDecodeError) as exc:
                reports.append({"league": league, "status": "unavailable", "detail": str(exc)})
    return reports
