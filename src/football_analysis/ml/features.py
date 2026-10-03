"""Leakage-safe pre-match features over the long-run, multi-division match history.

Every feature for a match is computed from state *before* that match date; the state
is updated only after the whole match day is processed. Fixtures (`is_future`) get
features but never update state.
"""

from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

TEAM_FEATURES = (
    "elo", "pi_rating", "ewm_points", "ewm_gf", "ewm_ga", "ewm_sot_for", "ewm_sot_against",
    "ewm_shots_for", "ewm_corners_for", "venue_ewm_points", "venue_ewm_gd", "rest_days",
    "season_matches", "promoted",
)
MATCH_FEATURES = ("elo_diff", "pi_expected_gd", "league_home_rate", "league_draw_rate", "league_goals", "season_progress")
FEATURES = (*MATCH_FEATURES, *(f"{side}_{name}" for side in ("home", "away") for name in TEAM_FEATURES))
MARKET_FEATURES = ("mkt_p_home", "mkt_p_draw", "mkt_p_away")
PASSTHROUGH = ("close_p_home", "close_p_draw", "close_p_away")
KEYS = ["league", "season", "match_date", "home_team", "away_team"]


@dataclass
class Params:
    elo_k: float = 20.0
    elo_home: float = 65.0
    elo_regress: float = 0.8
    pi_lambda: float = 0.035
    pi_gamma: float = 0.7
    half_life: float = 6.0  # matches
    league_window: int = 400  # matches for league-level base rates
    priors: dict = field(default_factory=lambda: {"gf": 1.35, "ga": 1.35, "sot": 4.3, "shots": 12.0, "corners": 5.0})


def _pi_goals(rating):
    return np.sign(rating) * (10 ** (abs(rating) / 3) - 1)


class _Team:
    __slots__ = ("elo", "pi_h", "pi_a", "ewm", "venue", "last", "season", "season_n", "league")

    def __init__(self, elo, priors):
        self.elo = elo
        self.pi_h = self.pi_a = 0.0
        self.ewm = {"points": 1.35, "gf": priors["gf"], "ga": priors["ga"], "sot_for": priors["sot"],
                    "sot_against": priors["sot"], "shots_for": priors["shots"], "corners_for": priors["corners"]}
        self.venue = {"Home": [1.6, 0.3], "Away": [1.1, -0.3]}  # points, goal difference
        self.last = None
        self.season = None
        self.season_n = 0
        self.league = None


def _outcome(hg, ag):
    return "H" if hg > ag else "A" if hg < ag else "D"


def _market(frame):
    """Opening market probabilities with the bookmaker margin removed."""
    odds = frame[["odds_open_home", "odds_open_draw", "odds_open_away"]].astype(float)
    inverse = 1 / odds.where(odds > 1)
    total = inverse.sum(axis=1, min_count=3)
    return inverse.div(total, axis=0).set_axis(list(MARKET_FEATURES), axis=1)


def build_features(matches: pd.DataFrame, params: Params | None = None) -> pd.DataFrame:
    """Return one row per input match: keys, FEATURES, market features and targets.

    Required columns: league, season, match_date, home_team, away_team, home_goals,
    away_goals. Optional: home/away sot, shots, corners, odds_open_*, is_future.
    Leagues sharing a `country` (e.g. E0/E1) share team state, so promoted clubs keep
    their form; `tier` (1/2) decides where an entering club's Elo starts.
    """
    p = params or Params()
    frame = matches.copy()
    frame["match_date"] = pd.to_datetime(frame.match_date)
    for column in ("is_future",):
        if column not in frame:
            frame[column] = False
    for column in ("home_sot", "away_sot", "home_shots", "away_shots", "home_corners", "away_corners",
                   "odds_open_home", "odds_open_draw", "odds_open_away"):
        if column not in frame:
            frame[column] = np.nan
    if "country" not in frame:
        frame["country"] = frame.league
    if "tier" not in frame:
        frame["tier"] = 1
    frame = frame.sort_values(["match_date", "league", "home_team", "away_team"], kind="stable").reset_index(drop=True)

    alpha = 1 - 0.5 ** (1 / p.half_life)
    teams: dict[tuple, _Team] = {}
    league_members: dict[tuple, set] = defaultdict(set)  # (league, season) -> teams
    league_final: dict[tuple, dict] = defaultdict(dict)  # (league, season) -> team -> latest elo
    tiers = dict(zip(frame.league, frame.tier))
    league_recent: dict[str, deque] = defaultdict(lambda: deque(maxlen=p.league_window))
    league_size: dict[tuple, int] = {}
    out = np.full((len(frame), len(FEATURES)), np.nan)

    def entry_elo(league, season, from_tier):
        """Clubs entering a league start at its previous-season bottom (promoted/new) or top (relegated)."""
        final = sorted(league_final.get((league, season - 1), {}).values())
        if len(final) < 6:
            return 1500.0
        return float(np.mean(final[-3:] if from_tier < tiers[league] else final[:3]))

    def team(country, name, league, season):
        key = (country, name)
        state = teams.get(key)
        if state is None:
            state = teams[key] = _Team(entry_elo(league, season, 99), p.priors)
        if state.season != season:
            if state.league is not None and state.league != league:
                state.elo = entry_elo(league, season, tiers[state.league])
            elif state.season is not None:
                state.elo = 1500 + p.elo_regress * (state.elo - 1500)
            state.season, state.season_n = season, 0
        return state

    for (match_date,), day in frame.groupby(["match_date"], sort=True):
        updates = []
        for index, row in day.iterrows():
            season, league = int(row.season), row.league
            for name in (row.home_team, row.away_team):
                league_members[(league, season)].add(name)
            home = team(row.country, row.home_team, league, season)
            away = team(row.country, row.away_team, league, season)
            recent = league_recent[league]
            size = league_size.get((league, season - 1)) or 20
            features = {
                "elo_diff": (home.elo + p.elo_home - away.elo) / 400,
                "pi_expected_gd": _pi_goals(home.pi_h) - _pi_goals(away.pi_a),
                "league_home_rate": np.mean([r[0] == "H" for r in recent]) if len(recent) > 50 else 0.45,
                "league_draw_rate": np.mean([r[0] == "D" for r in recent]) if len(recent) > 50 else 0.26,
                "league_goals": np.mean([r[1] for r in recent]) if len(recent) > 50 else 2.7,
                "season_progress": min(1.0, home.season_n / (2 * (size - 1))),
            }
            for side, state, venue in (("home", home, "Home"), ("away", away, "Away")):
                features.update({
                    f"{side}_elo": state.elo / 400,
                    f"{side}_pi_rating": state.pi_h if venue == "Home" else state.pi_a,
                    f"{side}_ewm_points": state.ewm["points"],
                    f"{side}_ewm_gf": state.ewm["gf"], f"{side}_ewm_ga": state.ewm["ga"],
                    f"{side}_ewm_sot_for": state.ewm["sot_for"], f"{side}_ewm_sot_against": state.ewm["sot_against"],
                    f"{side}_ewm_shots_for": state.ewm["shots_for"], f"{side}_ewm_corners_for": state.ewm["corners_for"],
                    f"{side}_venue_ewm_points": state.venue[venue][0], f"{side}_venue_ewm_gd": state.venue[venue][1],
                    f"{side}_rest_days": 14.0 if state.last is None else float(min(30, max(1, (match_date - state.last).days))),
                    f"{side}_season_matches": float(state.season_n),
                    f"{side}_promoted": float(state.league not in (None, league)),
                })
            out[index] = [features[name] for name in FEATURES]
            if not row.is_future:
                updates.append((row, home, away, league))

        for row, home, away, league in updates:
            hg, ag = int(row.home_goals), int(row.away_goals)
            result = _outcome(hg, ag)
            # Elo with goal-margin multiplier
            expected = 1 / (1 + 10 ** ((away.elo - home.elo - p.elo_home) / 400))
            actual = {"H": 1.0, "D": 0.5, "A": 0.0}[result]
            margin = 1.0 if abs(hg - ag) <= 1 else np.log10(abs(hg - ag) + 1) * 2.2
            change = p.elo_k * margin * (actual - expected)
            home.elo += change
            away.elo -= change
            # pi-ratings (Constantinou & Fenton 2013)
            error = (hg - ag) - (_pi_goals(home.pi_h) - _pi_goals(away.pi_a))
            psi = np.sign(error) * 3 * np.log10(1 + abs(error))
            old_hh, old_aa = home.pi_h, away.pi_a
            home.pi_h += psi * p.pi_lambda
            home.pi_a += (home.pi_h - old_hh) * p.pi_gamma
            away.pi_a -= psi * p.pi_lambda
            away.pi_h += (away.pi_a - old_aa) * p.pi_gamma
            # exponentially weighted form
            points = {"H": (3, 0), "D": (1, 1), "A": (0, 3)}[result]
            for state, venue, gf, ga, pts, sot_f, sot_a, shots_f, corners_f in (
                (home, "Home", hg, ag, points[0], row.home_sot, row.away_sot, row.home_shots, row.home_corners),
                (away, "Away", ag, hg, points[1], row.away_sot, row.home_sot, row.away_shots, row.away_corners),
            ):
                values = {"points": pts, "gf": gf, "ga": ga, "sot_for": sot_f, "sot_against": sot_a,
                          "shots_for": shots_f, "corners_for": corners_f}
                for name, value in values.items():
                    if pd.notna(value):
                        state.ewm[name] += alpha * (float(value) - state.ewm[name])
                state.venue[venue][0] += 2 * alpha * (pts - state.venue[venue][0])
                state.venue[venue][1] += 2 * alpha * ((gf - ga) - state.venue[venue][1])
                state.last = row.match_date
                state.season_n += 1
                state.league = league
            league_recent[league].append((result, hg + ag))
            league_final[(league, int(row.season))][row.home_team] = home.elo
            league_final[(league, int(row.season))][row.away_team] = away.elo
        for (league, season), members in league_members.items():
            league_size[(league, season)] = len(members)

    result = frame[[*KEYS, "country", "tier", "is_future"]].copy()
    result[list(FEATURES)] = out
    result = pd.concat([result, _market(frame)], axis=1)
    for column in PASSTHROUGH:
        result[column] = frame[column] if column in frame else np.nan
    completed = ~frame.is_future.astype(bool)
    result["home_goals"] = frame.home_goals.where(completed)
    result["away_goals"] = frame.away_goals.where(completed)
    result["outcome"] = np.where(
        completed, np.select([frame.home_goals > frame.away_goals, frame.home_goals < frame.away_goals], [0, 2], 1), -1,
    )
    return result
