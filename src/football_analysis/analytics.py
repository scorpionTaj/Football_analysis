"""Chronological, deterministic match analytics."""

from collections import defaultdict
from math import log10

import pandas as pd


def expected_score(rating, opponent_rating, home_adjustment=0.0):
    return 1 / (1 + 10 ** ((opponent_rating - rating - home_adjustment) / 400))


def elo_history(matches, initial=1500.0, k_factor=24.0, home_advantage=60.0):
    """Return pre/post-match Elo without using future results.

    Ratings are isolated by competition. Teams retain ratings between seasons, with
    a 25% regression toward 1500 at every season boundary. Matches on the same day
    are rated from the same pre-day snapshot so CSV row order cannot leak outcomes.
    """
    columns = [
        "league", "season", "match_date", "team", "opponent", "venue",
        "pre_elo", "post_elo", "elo_change",
    ]
    if matches.empty:
        return pd.DataFrame(columns=columns)

    required = {
        "league", "season", "match_date", "home_team", "away_team",
        "home_goals", "away_goals",
    }
    missing = required - set(matches.columns)
    if missing:
        raise ValueError(f"Elo input is missing columns: {sorted(missing)}")

    frame = matches.copy()
    frame["match_date"] = pd.to_datetime(frame.match_date)
    frame = frame.sort_values(["league", "season", "match_date", "home_team", "away_team"])
    output = []

    for league, league_games in frame.groupby("league", sort=True):
        ratings = defaultdict(lambda: float(initial))
        previous_season = None
        for season, season_games in league_games.groupby("season", sort=True):
            if previous_season is not None:
                for team in list(ratings):
                    ratings[team] = initial + 0.75 * (ratings[team] - initial)
            previous_season = season

            for match_date, day_games in season_games.groupby("match_date", sort=True):
                day_start = dict(ratings)
                changes = defaultdict(float)
                day_rows = []
                for match in day_games.itertuples(index=False):
                    home_pre = day_start.get(match.home_team, float(initial))
                    away_pre = day_start.get(match.away_team, float(initial))
                    home_expected = expected_score(home_pre, away_pre, home_advantage)
                    if match.home_goals > match.away_goals:
                        home_result = 1.0
                    elif match.home_goals < match.away_goals:
                        home_result = 0.0
                    else:
                        home_result = 0.5
                    goal_margin = abs(match.home_goals - match.away_goals)
                    margin = 1.0 if goal_margin <= 1 else log10(goal_margin + 1) * 2.2
                    change = k_factor * margin * (home_result - home_expected)
                    changes[match.home_team] += change
                    changes[match.away_team] -= change
                    day_rows.append((match, home_pre, away_pre, change))

                for team, change in changes.items():
                    ratings[team] = day_start.get(team, float(initial)) + change
                for match, home_pre, away_pre, change in day_rows:
                    output.extend([
                        {
                            "league": league, "season": int(season), "match_date": match_date,
                            "team": match.home_team, "opponent": match.away_team, "venue": "Home",
                            "pre_elo": home_pre, "post_elo": home_pre + change, "elo_change": change,
                        },
                        {
                            "league": league, "season": int(season), "match_date": match_date,
                            "team": match.away_team, "opponent": match.home_team, "venue": "Away",
                            "pre_elo": away_pre, "post_elo": away_pre - change, "elo_change": -change,
                        },
                    ])
    return pd.DataFrame(output, columns=columns)


def shot_coverage(matches):
    """Summarize explicit shot-field availability by league and season."""
    if matches.empty:
        return pd.DataFrame(columns=["league", "season", "matches", "shot_matches", "coverage_pct"])
    complete = matches[["home_shots", "away_shots", "home_sot", "away_sot"]].notna().all(axis=1)
    work = matches[["league", "season"]].copy()
    work["complete"] = complete.astype(int)
    result = work.groupby(["league", "season"], as_index=False).agg(
        matches=("complete", "size"), shot_matches=("complete", "sum"),
    )
    result["coverage_pct"] = 100 * result.shot_matches / result.matches
    return result


def team_shot_efficiency(team_matches, minimum_coverage=0.95):
    """Return team shot metrics only for groups meeting the coverage gate."""
    columns = [
        "league", "season", "team", "matches", "coverage_pct",
        "shots_per_match", "shot_accuracy_pct", "goals_per_shot_pct",
        "goals_per_sot_pct",
    ]
    if team_matches.empty:
        return pd.DataFrame(columns=columns)
    work = team_matches.copy()
    work["complete"] = work[["shots", "shots_on_target"]].notna().all(axis=1)
    rows = []
    for (league, season, team), group in work.groupby(["league", "season", "team"]):
        coverage = group.complete.mean()
        if coverage < minimum_coverage:
            continue
        valid = group[group.complete]
        shots, on_target = valid.shots.sum(), valid.shots_on_target.sum()
        rows.append({
            "league": league, "season": int(season), "team": team,
            "matches": len(group), "coverage_pct": 100 * coverage,
            "shots_per_match": shots / len(valid),
            "shot_accuracy_pct": 100 * on_target / shots if shots else None,
            "goals_per_shot_pct": 100 * valid.gf.sum() / shots if shots else None,
            "goals_per_sot_pct": 100 * valid.gf.sum() / on_target if on_target else None,
        })
    return pd.DataFrame(rows, columns=columns)
