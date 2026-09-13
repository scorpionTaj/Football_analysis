"""Canonical club identities shared across football data providers."""

import re


TEAM_NAMES = {
    "Barcelona": "FC Barcelona",
    "FC Barcelona": "FC Barcelona",
    "Ath Madrid": "Atlético Madrid",
    "Atlético Madrid": "Atlético Madrid",
    "Ath Bilbao": "Athletic Bilbao",
    "Athletic Bilbao": "Athletic Bilbao",
    "Betis": "Real Betis",
    "Real Betis": "Real Betis",
    "Man City": "Manchester City",
    "Manchester City": "Manchester City",
    "Man United": "Manchester United",
    "Manchester United": "Manchester United",
    "Newcastle": "Newcastle United",
    "Newcastle United": "Newcastle United",
    "Dortmund": "Borussia Dortmund",
    "Borussia Dortmund": "Borussia Dortmund",
    "Leverkusen": "Bayer Leverkusen",
    "Bayer Leverkusen": "Bayer Leverkusen",
    "Ein Frankfurt": "Eintracht Frankfurt",
    "Eintracht Frankfurt": "Eintracht Frankfurt",
    "RasenBallsport Leipzig": "RB Leipzig",
    "RB Leipzig": "RB Leipzig",
    "Paris SG": "Paris Saint-Germain",
    "Paris Saint-Germain": "Paris Saint-Germain",
    "Milan": "AC Milan",
    "AC Milan": "AC Milan",
    "Inter": "Inter Milan",
    "Inter Milan": "Inter Milan",
}


def display_team(name):
    """Return a stable user-facing club name while preserving unknown clubs."""
    if name is None:
        return ""
    value = str(name).strip()
    return TEAM_NAMES.get(value, value)


def team_key(name):
    """Return a provider-independent key for standings reconciliation."""
    return re.sub(r"[^a-z0-9]", "", display_team(name).casefold())
