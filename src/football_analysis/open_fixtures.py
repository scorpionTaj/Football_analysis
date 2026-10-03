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
PROVISIONAL_SOURCE = "OpenFootball results (CC0, provisional)"
BASE_URL = "https://raw.githubusercontent.com/openfootball/football.json/master"
LEAGUE_FILES = {
    "E0": "en.1.json", "SP1": "es.1.json", "D1": "de.1.json",
    "I1": "it.1.json", "F1": "fr.1.json", "N1": "nl.1.json",
    "P1": "pt.1.json",
}
# Football.TXT files (CC0) where OpenFootball has no JSON export; converted to the same
# document shape and passed through the same validation. Turkey has no 2026/27 file.
TXT_FILES = {
    "G1": "europe/master/greece/{season}-{yy}_gr1.txt",
    "B1": "belgium/master/{season}-{yy}/be1.txt",
}
TEAMS = {"E0": 20, "SP1": 20, "I1": 20, "D1": 18, "F1": 18, "N1": 18, "P1": 18,
         "B1": 18, "G1": 14}  # G1: regular season only (play-offs are drawn later)

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
    "Aris Thessaloniki": "Aris", "Iraklis 1908": "Iraklis", "OFI": "OFI Crete",
    "Olympiakos Piraeus": "Olympiakos", "Volos": "Volos NFC", "Levadiakos": "Levadeiakos",
    "KAA Gent": "Gent", "KRC Genk": "Genk", "KV Kortrijk": "Kortrijk", "KV Mechelen": "Mechelen",
    "KVC Westerlo": "Westerlo", "OH Leuven": "Oud-Heverlee Leuven", "RAAL La Louvière": "RAAL La Louviere",
    "Royal Antwerp FC": "Antwerp", "Royale Union Saint-Gilloise": "St. Gilloise",
    "RSC Anderlecht": "Anderlecht", "SK Beveren": "Beveren", "Sporting Charleroi": "Charleroi",
    "Standard de Liège": "Standard", "STVV": "St Truiden", "SV Zulte Waregem": "Waregem",
}


def _provider_key(name: str) -> str:
    return team_key(ALIASES.get(name, name))


_MONTHS = {m: i for i, m in enumerate(("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"), 1)}
_DATE = re.compile(r"(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun) ([A-Z][a-z]{2}) (\d{1,2})(?: (\d{4}))?")
_TIME = re.compile(r"(\d{1,2}:\d{2}|--:--)\s+")
_SCORED = re.compile(r"(?P<home>.+?)\s{2,}(?P<h>\d+)-(?P<a>\d+)(?:\s+\(\d+-\d+\))?\s{2,}(?P<away>.+)")
_VERSUS = re.compile(r"(?P<home>.+?)\s+v\s+(?P<away>.+?)(?:\s+(?P<h>\d+)-(?P<a>\d+))?")


def football_txt_to_json(text: str, season: int) -> bytes:
    """Football.TXT -> the football.json document shape. A match whose round has no
    published date gets date None, so validation rejects the calendar until it is dated."""
    matches, day, scorers = [], None, False
    for line in text.splitlines():
        line = line.split("#", 1)[0].strip()
        if (scorers and line) or line.startswith("("):  # scorers or a note, until ")" or a blank line
            scorers = not line.endswith(")")
            continue
        scorers = False
        if not line or line.startswith("="):
            continue
        if line.startswith("▪"):
            day = None  # every round states its own date; TBC rounds stay undated
            continue
        if found := _DATE.fullmatch(line):
            month = _MONTHS[found[1]]
            day = date(int(found[3] or (season if month >= 7 else season + 1)), month, int(found[2]))
            continue
        if line.startswith("TBC"):
            day = None
            continue
        time = _TIME.match(line)
        rest = line[time.end():] if time else line
        found = _SCORED.fullmatch(rest) or _VERSUS.fullmatch(rest)
        if not found:
            raise ValueError(f"Unrecognised Football.TXT line: {line[:60]}")
        scored = found["h"] is not None
        matches.append({
            "date": day.isoformat() if day else None,
            "time": time[1] if time and time[1] != "--:--" else None,
            "team1": found["home"].strip(), "team2": found["away"].strip(),
            **({"score": {"ft": [int(found["h"]), int(found["a"])]}} if scored else {}),
        })
    return json.dumps({"matches": matches}).encode()


def normalize_open_schedule(raw: bytes, league: str, season: int) -> pd.DataFrame:
    """Reject incomplete or malformed calendars before any stored partition changes."""
    if league not in TEAMS:
        raise ValueError(f"No OpenFootball schedule for {league}")
    document = json.loads(raw)
    matches = document.get("matches") if isinstance(document, dict) else None
    teams_expected = TEAMS[league]
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
            "home_goals": int(final[0]) if scored else None, "away_goals": int(final[1]) if scored else None,
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
        yy = str(season + 1)[-2:]
        path = self.cache_root / f"{season}-{yy}" / LEAGUE_FILES.get(league, f"{league.lower()}.json")
        if path.exists() and not self.refresh and datetime.fromtimestamp(path.stat().st_mtime) >= datetime.now() - timedelta(hours=12):
            return path.read_bytes()
        if league in TXT_FILES:
            url = f"https://raw.githubusercontent.com/openfootball/{TXT_FILES[league].format(season=season, yy=yy)}"
        else:
            url = f"{BASE_URL}/{season}-{yy}/{LEAGUE_FILES[league]}"
        response = self.session.get(url, timeout=(10, 45))
        response.raise_for_status()
        raw = response.content
        if league in TXT_FILES:
            raw = football_txt_to_json(raw.decode("utf-8"), season)
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
    leagues = leagues if leagues is not None else list(TEAMS)
    adapter = adapter or OpenFootballFixtures(refresh=refresh)
    reports = []
    with connect(db) as con:
        for league in leagues:
            if league not in TEAMS:
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
                # Scores OpenFootball already has but Football-Data has not published yet. They
                # carry no statistics and are replaced when the full Football-Data row arrives.
                published = {(h, a) for h, a in con.execute(
                    "SELECT home_team, away_team FROM recent_matches WHERE league=? AND season=? AND source<>?",
                    [league, season, PROVISIONAL_SOURCE]).fetchall()}
                provisional = pd.DataFrame([{
                    "league": league, "season": season, "match_date": row.match_date,
                    "home_team": known[row.home_key], "away_team": known[row.away_key],
                    "home_goals": row.home_goals, "away_goals": row.away_goals,
                    "source": PROVISIONAL_SOURCE, "fetched_at": now,
                } for row in full[full.scored & (full.match_date <= today)].itertuples(index=False)
                    if (known[row.home_key], known[row.away_key]) not in published],
                    columns=["league", "season", "match_date", "home_team", "away_team",
                             "home_goals", "away_goals", "source", "fetched_at"])
                con.register("incoming_provisional", provisional)
                con.register("incoming_open_fixtures", incoming)
                con.execute("BEGIN")
                try:
                    con.execute("DELETE FROM recent_events WHERE source=? AND league=? AND season=?", [SOURCE, league, season])
                    con.execute("DELETE FROM recent_matches WHERE source=? AND league=? AND season=?",
                                [PROVISIONAL_SOURCE, league, season])
                    con.execute("INSERT INTO recent_matches (league, season, match_date, home_team, away_team, "
                                "home_goals, away_goals, source, fetched_at) SELECT * FROM incoming_provisional")
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
                    con.unregister("incoming_provisional")
                reports.append({"league": league, "status": "success", "rows": len(rows), "provisional_results": len(provisional)})
            except (requests.RequestException, ValueError, UnicodeError, OSError, json.JSONDecodeError) as exc:
                reports.append({"league": league, "status": "unavailable", "detail": str(exc)})
    return reports
