from datetime import date
from pathlib import Path
import os

ROOT = Path(__file__).resolve().parents[2]
DATA = Path(os.environ.get("FOOTBALL_DATA_DIR", ROOT / "data"))
DB = DATA / "football.duckdb"
LEAGUES = {"E0": "Premier League", "SP1": "La Liga", "D1": "Bundesliga", "I1": "Serie A", "F1": "Ligue 1"}
CLUBS = {"Real Madrid": "Real Madrid", "Barcelona": "FC Barcelona", "Ath Madrid": "Atlético Madrid", "Man City": "Manchester City", "Liverpool": "Liverpool", "Arsenal": "Arsenal", "Bayern Munich": "Bayern Munich", "Dortmund": "Borussia Dortmund", "Paris SG": "Paris Saint-Germain", "Inter": "Inter Milan", "Milan": "AC Milan", "Juventus": "Juventus"}

def seasons(today=None):
    """European July rollover; source completeness is checked independently."""
    today = today or date.today()
    last = today.year - (1 if today.month >= 7 else 2)
    return list(range(last - 4, last + 1))

def label(year):
    return f"{year}/{str(year + 1)[-2:]}"

def expected_teams(league, year):
    return 18 if league == "D1" or (league == "F1" and year >= 2023) else 20
