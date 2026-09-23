"""Prediction data engineering: canonical matches and leakage-safe pre-match features."""

from __future__ import annotations

from collections import defaultdict, deque

import numpy as np
import pandas as pd

from .teams import team_key

FEATURES = (
    "elo_gap", "home_form_ppg", "away_form_ppg", "home_goals_for",
    "away_goals_for", "home_goals_against", "away_goals_against",
    "home_rest_days", "away_rest_days", "home_sot_for", "away_sot_for",
    "home_sot_against", "away_sot_against",
)
FORM_WINDOW = 10
PRIOR_SEASON_FORM_MATCHES = 5


def load_match_inputs(con):
    """Prefer refreshed current results over older historical copies."""
    historical = con.sql("SELECT * FROM matches").df()
    recent = con.sql("SELECT * FROM recent_matches").df()
    matches = pd.concat([historical, recent], ignore_index=True).drop_duplicates(
        ["league", "season", "home_team", "away_team"], keep="last",
    )
    fixtures = con.sql("""
        SELECT league, season, match_date, home_team, away_team, event_kind, fetched_at
        FROM recent_events
        WHERE event_kind IN ('next', 'fixture') AND match_date >= current_date
    """).df()
    if not fixtures.empty:
        fixtures["home_key"] = fixtures.home_team.map(team_key)
        fixtures["away_key"] = fixtures.away_team.map(team_key)
        fixtures["priority"] = fixtures.event_kind.map({"fixture": 0, "next": 1})
        fixtures = fixtures.sort_values(["priority", "fetched_at"], ascending=[True, False]).drop_duplicates(
            ["league", "season", "home_key", "away_key"], keep="first",
        )
        completed = set(zip(
            matches.league, matches.season,
            matches.home_team.map(team_key), matches.away_team.map(team_key),
        ))
        fixtures = fixtures[[
            (row.league, row.season, row.home_key, row.away_key) not in completed
            for row in fixtures.itertuples(index=False)
        ]][["league", "season", "match_date", "home_team", "away_team"]]
    return matches, fixtures


def _form(history, key, window):
    rows = list(history[key])[-window:]
    if not rows:
        return 1.0, 1.2, 1.2, 4.4, 4.4
    shots_for = [row[3] for row in rows if pd.notna(row[3])]
    shots_against = [row[4] for row in rows if pd.notna(row[4])]
    return (
        sum(row[0] for row in rows) / len(rows),
        sum(row[1] for row in rows) / len(rows),
        sum(row[2] for row in rows) / len(rows),
        sum(shots_for) / len(shots_for) if shots_for else 4.4,
        sum(shots_against) / len(shots_against) if shots_against else 4.4,
    )


def _rest(last_played, key, match_date):
    previous = last_played.get(key)
    return 14.0 if previous is None else float(min(30, max(1, (match_date - previous).days)))


def build_match_features(matches, form_window=FORM_WINDOW):
    """Create pre-match features; same-day results never affect one another."""
    required = {
        "league", "season", "match_date", "home_team", "away_team",
        "home_goals", "away_goals",
    }
    missing = required - set(matches.columns)
    if missing:
        raise ValueError(f"Prediction input is missing: {', '.join(sorted(missing))}")
    work = matches.copy()
    if "is_future" not in work:
        work["is_future"] = False
    work["match_date"] = pd.to_datetime(work.match_date)
    work = work.sort_values(["league", "season", "match_date", "home_team", "away_team"])
    records = []
    for league, league_matches in work.groupby("league", sort=True):
        ratings = defaultdict(lambda: 1500.0)
        history = defaultdict(lambda: deque(maxlen=form_window))
        last_played = {}
        previous_season = None
        for season, season_matches in league_matches.groupby("season", sort=True):
            if previous_season is not None:
                for key in list(ratings):
                    ratings[key] = 1500 + 0.75 * (ratings[key] - 1500)
                if season == previous_season + 1:
                    for key in list(history):
                        history[key] = deque(
                            list(history[key])[-min(form_window, PRIOR_SEASON_FORM_MATCHES):],
                            maxlen=form_window,
                        )
                else:
                    history.clear()
            previous_season = season
            for match_date, day_matches in season_matches.groupby("match_date", sort=True):
                date = pd.Timestamp(match_date)
                day_rows = []
                changes = defaultdict(float)
                for match in day_matches.itertuples(index=False):
                    home_key, away_key = team_key(match.home_team), team_key(match.away_team)
                    home_ppg, home_gf, home_ga, home_sot_for, home_sot_against = _form(
                        history, home_key, form_window,
                    )
                    away_ppg, away_gf, away_ga, away_sot_for, away_sot_against = _form(
                        history, away_key, form_window,
                    )
                    home_elo, away_elo = ratings[home_key], ratings[away_key]
                    features = [
                        (home_elo + 60 - away_elo) / 400,
                        home_ppg / 3, away_ppg / 3, home_gf, away_gf, home_ga, away_ga,
                        _rest(last_played, home_key, date), _rest(last_played, away_key, date),
                        home_sot_for, away_sot_for, home_sot_against, away_sot_against,
                    ]
                    is_future = bool(match.is_future)
                    result = None if is_future else (
                        "Home" if match.home_goals > match.away_goals
                        else "Away" if match.home_goals < match.away_goals else "Draw"
                    )
                    records.append({
                        "league": league, "season": int(season), "match_date": date,
                        "home_team": match.home_team, "away_team": match.away_team,
                        **dict(zip(FEATURES, features)), "actual_result": result,
                    })
                    if is_future:
                        continue
                    expected = 1 / (1 + 10 ** ((away_elo - home_elo - 60) / 400))
                    actual = 1.0 if result == "Home" else 0.0 if result == "Away" else 0.5
                    margin = max(1.0, np.log10(abs(match.home_goals - match.away_goals) + 1) * 2.2)
                    change = 24 * margin * (actual - expected)
                    changes[home_key] += change
                    changes[away_key] -= change
                    home_points = 3 if result == "Home" else 1 if result == "Draw" else 0
                    away_points = 3 if result == "Away" else 1 if result == "Draw" else 0
                    day_rows.append((
                        home_key, away_key, home_points, away_points,
                        match.home_goals, match.away_goals,
                        getattr(match, "home_sot", None), getattr(match, "away_sot", None),
                    ))
                for key, change in changes.items():
                    ratings[key] += change
                for home_key, away_key, hp, ap, hg, ag, hsot, asot in day_rows:
                    history[home_key].append((hp, hg, ag, hsot, asot))
                    history[away_key].append((ap, ag, hg, asot, hsot))
                    last_played[home_key] = date
                    last_played[away_key] = date
    return pd.DataFrame(records)


def future_features(matches, fixtures, form_window=FORM_WINDOW):
    """Build fixture features from the latest known pre-match state without outcomes."""
    if fixtures.empty:
        return pd.DataFrame(columns=["league", "season", "match_date", "home_team", "away_team", *FEATURES])
    sentinel = fixtures.copy()
    sentinel["home_goals"] = 0
    sentinel["away_goals"] = 0
    sentinel["is_future"] = True
    history = matches.copy()
    history["is_future"] = False
    combined = pd.concat([history, sentinel], ignore_index=True)
    features = build_match_features(combined, form_window=form_window)
    keys = sentinel[["league", "season", "match_date", "home_team", "away_team"]].copy()
    keys["match_date"] = pd.to_datetime(keys.match_date)
    return keys.merge(
        features[features.actual_result.isna()].drop(columns="actual_result"),
        on=["league", "season", "match_date", "home_team", "away_team"], how="left",
    )
