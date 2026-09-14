from datetime import date
from pathlib import Path
import os

ROOT = Path(__file__).resolve().parents[2]
DATA = Path(os.environ.get("FOOTBALL_DATA_DIR", ROOT / "data"))
DB = DATA / "football.duckdb"
LEAGUES = {"E0": "Premier League", "SP1": "La Liga", "D1": "Bundesliga", "I1": "Serie A", "F1": "Ligue 1"}
RECENT_LEAGUES = {
    **LEAGUES,
    "N1": "Eredivisie",
    "P1": "Primeira Liga",
    "B1": "Belgian Pro League",
    "T1": "Turkish Süper Lig",
    "G1": "Greek Super League",
}
TOURNAMENTS = {
    "UCL": "UEFA Champions League",
    "CWC": "FIFA Club World Cup",
    "WC": "FIFA World Cup",
}
CALENDAR_YEAR_TOURNAMENTS = {"CWC", "WC"}
COMPETITIONS = {**RECENT_LEAGUES, **TOURNAMENTS}
THESPORTSDB_LEAGUE_IDS = {
    "E0": 4328, "D1": 4331, "I1": 4332, "F1": 4334, "SP1": 4335,
    "G1": 4336, "N1": 4337, "B1": 4338, "T1": 4339, "P1": 4344,
    "UCL": 4480, "WC": 4429,
}
CLUBS = {"Real Madrid": "Real Madrid", "Barcelona": "FC Barcelona", "Ath Madrid": "Atlético Madrid", "Man City": "Manchester City", "Liverpool": "Liverpool", "Arsenal": "Arsenal", "Bayern Munich": "Bayern Munich", "Dortmund": "Borussia Dortmund", "Paris SG": "Paris Saint-Germain", "Inter": "Inter Milan", "Milan": "AC Milan", "Juventus": "Juventus"}

def seasons(today=None):
    """European July rollover; source completeness is checked independently."""
    today = today or date.today()
    last = today.year - (1 if today.month >= 7 else 2)
    return list(range(last - 4, last + 1))


def current_season(today=None):
    today = today or date.today()
    return today.year if today.month >= 7 else today.year - 1

def label(year):
    return f"{year}/{str(year + 1)[-2:]}"

def expected_teams(league, year):
    return 18 if league == "D1" or (league == "F1" and year >= 2023) else 20
