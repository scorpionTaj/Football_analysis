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
    "UEL": "UEFA Europa League",
    "UECL": "UEFA Conference League",
    "USC": "UEFA Super Cup",
    "FAC": "FA Cup",
    "EFL": "Carabao Cup",
    "GBCS": "FA Community Shield",
    "CDR": "Copa del Rey",
    "SUC": "Supercopa de España",
    "DFB": "DFB-Pokal",
    "CIT": "Coppa Italia",
    "NLP": "KNVB Cup",
    "EURO": "UEFA European Championship",
    "COPA": "Copa América",
    "AFCON": "Africa Cup of Nations",
    "ASIAN": "AFC Asian Cup",
    "CWC": "FIFA Club World Cup",
    "WC": "FIFA World Cup",
}
OPENFOOTBALL_TOURNAMENTS = {"UCL", "CWC", "WC"}
CALENDAR_YEAR_TOURNAMENTS = {"CWC", "WC", "EURO", "COPA", "AFCON", "ASIAN"}
COMPETITIONS = {**RECENT_LEAGUES, **TOURNAMENTS}
COMPETITION_GROUPS = {
    **{code: "Domestic leagues" for code in RECENT_LEAGUES},
    **{code: "Domestic cups" for code in ("FAC", "EFL", "GBCS", "CDR", "SUC", "DFB", "CIT", "NLP")},
    **{code: "Continental clubs" for code in ("UCL", "UEL", "UECL", "USC")},
    **{code: "International teams" for code in ("WC", "EURO", "COPA", "AFCON", "ASIAN")},
    "CWC": "World club competitions",
}
COMPETITION_REGIONS = {
    **{code: "England" for code in ("E0", "FAC", "EFL", "GBCS")},
    **{code: "Spain" for code in ("SP1", "CDR", "SUC")},
    **{code: "Germany" for code in ("D1", "DFB")},
    **{code: "Italy" for code in ("I1", "CIT")},
    **{code: "Netherlands" for code in ("N1", "NLP")},
    **{code: "Europe" for code in ("UCL", "UEL", "UECL", "USC", "EURO")},
    **{code: "International" for code in ("WC", "CWC", "COPA", "AFCON", "ASIAN")},
}
# Published Transfermarkt competition ids mapped to the app's stable codes.
TRANSFERMARKT_COMPETITIONS = {
    "GB1": "E0", "ES1": "SP1", "L1": "D1", "IT1": "I1", "FR1": "F1",
    "NL1": "N1", "PO1": "P1", "BE1": "B1", "TR1": "T1", "GR1": "G1",
    "CL": "UCL", "EL": "UEL", "UCOL": "UECL", "USC": "USC",
    "FAC": "FAC", "GBCS": "GBCS", "CDR": "CDR", "SUC": "SUC",
    "DFB": "DFB", "CIT": "CIT", "NLP": "NLP",
    "EURO": "EURO", "COPA": "COPA", "AFCN": "AFCON", "AFAC": "ASIAN",
    "FIWC": "WC",
}
TRANSFERMARKT_TOURNAMENT_CODES = set(TOURNAMENTS) - {"CWC"}
THESPORTSDB_LEAGUE_IDS = {
    "E0": 4328, "D1": 4331, "I1": 4332, "F1": 4334, "SP1": 4335,
    "G1": 4336, "N1": 4337, "B1": 4338, "T1": 4339, "P1": 4344,
    "UCL": 4480, "UEL": 4481, "UECL": 5071, "WC": 4429,
    "FAC": 4482, "EFL": 4570, "CDR": 4483, "SUC": 4511,
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
