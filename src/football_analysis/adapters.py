"""Free public CSV transport, local replay, and strict source normalization."""
from dataclasses import dataclass
from datetime import datetime
from hashlib import sha256
from io import StringIO
from pathlib import Path
from typing import Protocol
import time
import pandas as pd
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from .config import expected_teams

@dataclass
class Batch:
    frame: pd.DataFrame
    url: str
    digest: str

class Adapter(Protocol):
    def fetch(self, league: str, year: int) -> Batch: ...


def normalize(raw, league, year, url, require_complete=True):
    df = pd.read_csv(StringIO(raw.decode("utf-8-sig")))
    required = {"Div", "Date", "HomeTeam", "AwayTeam", "FTHG", "FTAG", "FTR"}
    if not required.issubset(df.columns):
        raise ValueError(f"Missing columns: {required - set(df.columns)}")
    df = df.dropna(how="all")
    if require_complete and df[list(required)].isna().any().any():
        raise ValueError("Missing result or fixture fields; season may be unfinished")
    if not require_complete:
        df = df.dropna(subset=["Div", "Date", "HomeTeam", "AwayTeam", "FTHG", "FTAG", "FTR"])
        if df.empty:
            raise ValueError("No completed matches are available for this season")
    if not df.Div.eq(league).all():
        raise ValueError("Unexpected league in source")
    df["match_date"] = pd.to_datetime(df.Date, dayfirst=True, format="mixed", errors="raise").dt.date
    if not all(datetime(year, 7, 1).date() <= d <= datetime(year+1, 6, 30).date() for d in df.match_date):
        raise ValueError("Dates outside requested season")
    for col in ["HomeTeam", "AwayTeam"]:
        df[col] = df[col].str.strip()
        if df[col].eq("").any():
            raise ValueError("Empty team name")
    optional_integers = [
        "HTHG", "HTAG", "HS", "AS", "HST", "AST", "HC", "AC",
        "HF", "AF", "HY", "AY", "HR", "AR",
    ]
    for col in ["FTHG", "FTAG", *optional_integers]:
        if col not in df:
            df[col] = float("nan")
        values = pd.to_numeric(df[col], errors="raise")
        if ((values.dropna() < 0) | (values.dropna() % 1 != 0)).any():
            raise ValueError(f"Invalid nonnegative integer: {col}")
        df[col] = values
    # Some historical source rows contain impossible shot combinations. Keep the
    # result, but quarantine the affected shot side so downstream coverage gates
    # exclude it instead of presenting a misleading efficiency value.
    invalid_home_shots = df.HS.notna() & df.HST.notna() & (df.HST > df.HS)
    invalid_away_shots = df.AS.notna() & df.AST.notna() & (df.AST > df.AS)
    df.loc[invalid_home_shots, ["HS", "HST"]] = float("nan")
    df.loc[invalid_away_shots, ["AS", "AST"]] = float("nan")
    outcomes = df.apply(lambda r: "H" if r.FTHG > r.FTAG else "A" if r.FTHG < r.FTAG else "D", axis=1)
    if not outcomes.eq(df.FTR).all():
        raise ValueError("Result disagrees with score")
    teams = set(df.HomeTeam) | set(df.AwayTeam)
    n = expected_teams(league, year)
    pairs = set(zip(df.HomeTeam, df.AwayTeam))
    if require_complete and (len(teams) != n or len(df) != n*(n-1) or len(pairs) != len(df) or any(a == b for a,b in pairs)):
        raise ValueError(f"Incomplete/invalid season: {len(df)} results, expected {n*(n-1)}; {len(teams)} teams, expected {n}")
    if len(pairs) != len(df) or any(a == b for a, b in pairs):
        raise ValueError("Duplicate or self-referencing fixtures in source")
    if "Referee" not in df:
        df["Referee"] = ""
    df["Referee"] = df.Referee.fillna("").astype(str).str.strip()
    df = df.rename(columns={
        "HomeTeam": "home_team", "AwayTeam": "away_team",
        "FTHG": "home_goals", "FTAG": "away_goals",
        "HTHG": "half_time_home_goals", "HTAG": "half_time_away_goals",
        "HS": "home_shots", "AS": "away_shots", "HST": "home_sot", "AST": "away_sot",
        "HC": "home_corners", "AC": "away_corners", "HF": "home_fouls", "AF": "away_fouls",
        "HY": "home_yellows", "AY": "away_yellows", "HR": "home_reds", "AR": "away_reds",
        "Referee": "referee",
    })
    df["league"] = league
    df["season"] = year
    cols = [
        "league", "season", "match_date", "home_team", "away_team",
        "home_goals", "away_goals", "home_shots", "away_shots", "home_sot", "away_sot",
        "half_time_home_goals", "half_time_away_goals", "home_corners", "away_corners",
        "home_fouls", "away_fouls", "home_yellows", "away_yellows", "home_reds", "away_reds",
        "referee",
    ]
    return Batch(df[cols], url, sha256(raw).hexdigest())

class FootballDataCSV:
    def __init__(self, cache: Path, refresh=False, require_complete=True, max_age=None):
        self.cache, self.refresh, self.require_complete = cache, refresh, require_complete
        self.max_age = max_age
        self.session = requests.Session()
        self.session.headers["User-Agent"] = "football-analysis/0.4 (personal research; cached CSV)"
        retry = Retry(total=3, backoff_factor=1, status_forcelist=[429,500,502,503,504], respect_retry_after_header=True)
        self.session.mount("https://", HTTPAdapter(max_retries=retry))

    def fetch(self, league, year):
        code = f"{year%100:02d}{(year+1)%100:02d}"
        url = f"https://www.football-data.co.uk/mmz4281/{code}/{league}.csv"
        path = self.cache / code / f"{league}.csv"
        cached = path.exists() and not self.refresh and (
            self.max_age is None or time.time() - path.stat().st_mtime < self.max_age.total_seconds()
        )
        if cached:
            raw = path.read_bytes()
        else:
            response = self.session.get(url, timeout=(10, 60))
            response.raise_for_status()
            raw = response.content
            time.sleep(1)  # Conservative courtesy interval, not a claimed provider quota.
        batch = normalize(raw, league, year, url, require_complete=self.require_complete)
        if not cached:
            path.parent.mkdir(parents=True, exist_ok=True)
            tmp = path.with_suffix(".tmp")
            tmp.write_bytes(raw)
            tmp.replace(path)
        return batch

class LocalCSV:
    """Offline replay of previously downloaded Football-Data CSV files."""
    def __init__(self, directory):
        self.directory = Path(directory)
    def fetch(self, league, year):
        code = f"{year%100:02d}{(year+1)%100:02d}"
        path = self.directory / code / f"{league}.csv"
        return normalize(path.read_bytes(), league, year, str(path))
