"""No-key tournament ingestion through OpenFootball's CC0 feeds."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import time
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Iterable

import pandas as pd
import requests

from .config import DATA, DB, OPENFOOTBALL_TOURNAMENTS, current_season
from .ingest import connect
from .sync_state import cached_fingerprint, mark_fresh

SOURCE = "OpenFootball (CC0)"
UCL_SEASONS = tuple(range(2021, current_season() + 1))  # the current file appears once OpenFootball starts it
WORLD_CUPS = (2018, 2022, 2026)
CLUB_WORLD_CUPS = (2025,)


@dataclass(frozen=True)
class TournamentBatch:
    frame: pd.DataFrame
    url: str
    digest: str
    goals: pd.DataFrame = field(default_factory=lambda: pd.DataFrame(columns=[
        "competition", "season", "match_date", "team", "player", "minute",
        "penalty", "own_goal", "source", "source_url", "fetched_at",
    ]))


def _season_slug(year: int) -> str:
    return f"{year}-{str(year + 1)[-2:]}"


def _empty_frame() -> pd.DataFrame:
    return pd.DataFrame(columns=[
        "competition", "season", "stage", "group_name", "match_date",
        "home_team", "away_team", "home_goals", "away_goals",
        "home_penalties", "away_penalties", "venue", "neutral", "status",
        "source", "source_url", "fetched_at",
    ])


def parse_champions_league(raw: bytes, season: int, url: str = "memory") -> TournamentBatch:
    """Parse OpenFootball's human-readable Champions League match list."""
    text = raw.decode("utf-8-sig")
    stage = "Unknown"
    match_date = None
    rows = []
    date_re = re.compile(
        r"^\s*(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun)\s+([A-Z][a-z]{2})\s+(\d{1,2})(?:\s+(\d{4}))?\s*$"
    )
    match_re = re.compile(
        r"^\s*(?:(\d{1,2}:\d{2})\s+)?(.+?\([A-Z]{3}\))\s+v\s+(.+?\([A-Z]{3}\))\s+(\d+)-(\d+)(.*)$"
    )
    month_numbers = {month: index for index, month in enumerate(
        ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"), 1
    )}
    now = datetime.now()

    for line in text.splitlines():
        stage_match = re.match(r"^\s*▪\s*(.+?)\s*$", line)
        if stage_match:
            stage = stage_match.group(1)
            continue
        date_match = date_re.match(line)
        if date_match:
            month, day, explicit_year = date_match.groups()
            year = int(explicit_year) if explicit_year else season + (month_numbers[month] <= 6)
            match_date = pd.Timestamp(year=year, month=month_numbers[month], day=int(day)).date()
            continue
        fixture = match_re.match(line)
        if not fixture or match_date is None:
            continue
        _, home, away, home_goals, away_goals, suffix = fixture.groups()
        home = re.sub(r"\s+\([A-Z]{3}\)$", "", home).strip()
        away = re.sub(r"\s+\([A-Z]{3}\)$", "", away).strip()
        penalty = re.search(r"(?:pen(?:\.|alties)?\s*)?(\d+)-(\d+)\s*pen", suffix, re.I)
        rows.append({
            "competition": "UCL", "season": season, "stage": stage,
            "group_name": stage.split(",", 1)[0] if stage.startswith("Group ") else "",
            "match_date": match_date, "home_team": home, "away_team": away,
            "home_goals": int(home_goals), "away_goals": int(away_goals),
            "home_penalties": int(penalty.group(1)) if penalty else None,
            "away_penalties": int(penalty.group(2)) if penalty else None,
            "venue": "", "neutral": False, "status": "FINISHED",
            "source": SOURCE, "source_url": url, "fetched_at": now,
        })

    frame = pd.DataFrame(rows) if rows else _empty_frame()
    if frame.empty:
        raise ValueError(f"No completed Champions League matches found for {_season_slug(season)}")
    if frame.duplicated(["competition", "season", "match_date", "home_team", "away_team"]).any():
        raise ValueError("Duplicate Champions League matches in source")
    return TournamentBatch(frame, url, hashlib.sha256(raw).hexdigest())


def parse_world_cup(
    raw: bytes,
    year: int,
    url: str = "memory",
    competition: str = "WC",
) -> TournamentBatch:
    """Parse OpenFootball's structured World Cup-family JSON feeds."""
    document = json.loads(raw)
    matches = document.get("matches", document) if isinstance(document, dict) else document
    now = datetime.now()
    rows = []
    goal_rows = []
    for match in matches:
        score = match.get("score") or {}
        if isinstance(score, list):
            outcome = score
            penalties = [None, None]
        else:
            outcome = score.get("et") or score.get("ft")
            penalties = score.get("p") or [None, None]
        if not outcome or any(value is None for value in outcome):
            continue
        rows.append({
            "competition": competition, "season": year,
            "stage": match.get("round") or "Unknown",
            "group_name": match.get("group") or "",
            "match_date": pd.to_datetime(match["date"]).date(),
            "home_team": match["team1"], "away_team": match["team2"],
            "home_goals": int(outcome[0]), "away_goals": int(outcome[1]),
            "home_penalties": None if penalties[0] is None else int(penalties[0]),
            "away_penalties": None if penalties[1] is None else int(penalties[1]),
            "venue": match.get("ground") or "", "neutral": True,
            "status": "FINISHED", "source": SOURCE, "source_url": url,
            "fetched_at": now,
        })
        for side, team in (("goals1", match["team1"]), ("goals2", match["team2"])):
            for goal in match.get(side) or []:
                goal_rows.append({
                    "competition": competition, "season": year,
                    "match_date": pd.to_datetime(match["date"]).date(),
                    "team": team, "player": goal.get("name") or "Unknown",
                    "minute": str(goal.get("minute") or ""),
                    "penalty": bool(goal.get("penalty", False)),
                    "own_goal": bool(goal.get("owngoal", False)),
                    "source": SOURCE, "source_url": url, "fetched_at": now,
                })
    frame = pd.DataFrame(rows) if rows else _empty_frame()
    if frame.empty:
        raise ValueError(f"No completed {competition} matches found for {year}")
    if frame.duplicated(["competition", "season", "match_date", "home_team", "away_team"]).any():
        raise ValueError("Duplicate World Cup matches in source")
    goals = pd.DataFrame(goal_rows, columns=TournamentBatch.__dataclass_fields__["goals"].default_factory().columns)
    return TournamentBatch(frame, url, hashlib.sha256(raw).hexdigest(), goals)


class OpenFootballTournaments:
    """Fetches a competition partition while hiding URL, cache and format details."""

    def __init__(self, cache: Path | None = None, refresh: bool = False, session=None):
        self.cache = Path(cache or DATA / "tournaments")
        self.refresh = refresh
        self.session = session or requests.Session()

    def fetch(self, competition: str, season: int) -> TournamentBatch:
        if competition == "UCL":
            url = (
                "https://raw.githubusercontent.com/openfootball/champions-league/"
                f"master/{_season_slug(season)}/cl.txt"
            )
            suffix = "txt"
            parser = parse_champions_league
        elif competition == "WC":
            url = (
                "https://raw.githubusercontent.com/openfootball/worldcup.json/"
                f"master/{season}/worldcup.json"
            )
            suffix = "json"
            parser = parse_world_cup
        elif competition == "CWC":
            url = (
                "https://raw.githubusercontent.com/openfootball/worldcup.json/"
                f"master/{season}/clubworldcup.json"
            )
            suffix = "json"
            parser = lambda raw, year, source_url: parse_world_cup(
                raw, year, source_url, competition="CWC",
            )
        else:
            raise ValueError(f"Unsupported tournament: {competition}")

        path = self.cache / competition.lower() / f"{season}.{suffix}"
        # Completed editions are immutable; a running one is re-downloaded once a day.
        stale = is_live(competition, season) and time.time() - path.stat().st_mtime > 86400 if path.exists() else True
        if not stale and not self.refresh:
            raw = path.read_bytes()
        else:
            response = self.session.get(url, timeout=45)
            response.raise_for_status()
            raw = response.content
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(raw)
        return parser(raw, season, url)


def is_live(competition: str, season: int) -> bool:
    return season >= (current_season() if competition == "UCL" else date.today().year)


def live_partitions() -> list[tuple[str, int]]:
    return [(competition, season) for competition, season in default_partitions() if is_live(competition, season)]


def default_partitions() -> list[tuple[str, int]]:
    return (
        [("UCL", season) for season in UCL_SEASONS]
        + [("CWC", year) for year in CLUB_WORLD_CUPS]
        + [("WC", year) for year in WORLD_CUPS]
    )


def sync_tournaments(
    db=DB,
    partitions: Iterable[tuple[str, int]] | None = None,
    adapter: OpenFootballTournaments | None = None,
):
    """Atomically replace each requested tournament partition."""
    adapter = adapter or OpenFootballTournaments()
    report = []
    with connect(db) as con:
        for competition, season in partitions or default_partitions():
            try:
                batch = adapter.fetch(competition, season)
                key = f"tournament:{competition}:{season}"
                content = batch.frame.drop(columns="fetched_at", errors="ignore")
                fingerprint = hashlib.sha256(
                    batch.digest.encode()
                    + pd.util.hash_pandas_object(content, index=False).values.tobytes()
                ).hexdigest()
                existing_count = con.execute(
                    "SELECT count(*) FROM tournament_matches WHERE competition=? AND season=?",
                    [competition, season],
                ).fetchall()[0][0]
                if cached_fingerprint(con, key) == fingerprint and existing_count == len(batch.frame):
                    report.append({
                        "competition": competition, "season": season,
                        "status": "cached", "rows": len(batch.frame),
                    })
                    print(report[-1], flush=True)
                    continue
                con.register("incoming_tournament", batch.frame)
                if not batch.goals.empty:
                    con.register("incoming_tournament_goals", batch.goals)
                con.execute("BEGIN")
                try:
                    con.execute(
                        "DELETE FROM tournament_matches WHERE competition=? AND season=?",
                        [competition, season],
                    )
                    con.execute("INSERT INTO tournament_matches SELECT * FROM incoming_tournament")
                    con.execute(
                        "DELETE FROM tournament_goals WHERE competition=? AND season=?",
                        [competition, season],
                    )
                    if not batch.goals.empty:
                        con.execute("INSERT INTO tournament_goals SELECT * FROM incoming_tournament_goals")
                    mark_fresh(con, key, fingerprint)
                    con.execute("COMMIT")
                except Exception:
                    con.execute("ROLLBACK")
                    raise
                finally:
                    con.unregister("incoming_tournament")
                    if not batch.goals.empty:
                        con.unregister("incoming_tournament_goals")
                report.append({
                    "competition": competition, "season": season,
                    "status": "success", "rows": len(batch.frame),
                })
            except Exception as exc:
                # A live edition OpenFootball has not started yet (404) is expected, not a failure.
                missing = getattr(getattr(exc, "response", None), "status_code", None) == 404
                report.append({
                    "competition": competition, "season": season,
                    "status": "pending" if missing and is_live(competition, season) else "failed", "detail": str(exc),
                })
            print(json.dumps(report[-1]), flush=True)
    return report


def main():
    parser = argparse.ArgumentParser(description="Sync free continental and world tournament results")
    parser.add_argument("--refresh", action="store_true")
    parser.add_argument("--competition", choices=sorted(OPENFOOTBALL_TOURNAMENTS))
    parser.add_argument("--seasons", nargs="+", type=int)
    args = parser.parse_args()
    if args.competition:
        defaults = {
            "UCL": UCL_SEASONS,
            "CWC": CLUB_WORLD_CUPS,
            "WC": WORLD_CUPS,
        }[args.competition]
        partitions = [(args.competition, year) for year in (args.seasons or defaults)]
    else:
        partitions = default_partitions()
    result = sync_tournaments(
        partitions=partitions,
        adapter=OpenFootballTournaments(refresh=args.refresh),
    )
    raise SystemExit(1 if any(row["status"] == "failed" for row in result) else 0)


if __name__ == "__main__":
    main()
