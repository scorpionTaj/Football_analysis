"""Reusable match-analysis interface for Streamlit and future HTTP frontends."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


@dataclass(frozen=True)
class AnalysisRequest:
    competitions: tuple[str, ...] = ()
    seasons: tuple[int, ...] = ()
    teams: tuple[str, ...] = ()
    venue: str | None = None
    form_window: int = 5


@dataclass(frozen=True)
class AnalysisReport:
    matches: pd.DataFrame
    rankings: pd.DataFrame
    form: pd.DataFrame
    correlations: pd.DataFrame


def tournament_team_matches(matches: pd.DataFrame) -> pd.DataFrame:
    """Expand neutral tournament fixtures into one analytical row per team."""
    if matches.empty:
        return pd.DataFrame(columns=[
            "league", "season", "match_date", "team", "opponent", "venue",
            "gf", "ga", "shots", "shots_on_target", "points",
        ])
    base = matches.rename(columns={"competition": "league"})
    home = pd.DataFrame({
        "league": base.league, "season": base.season, "match_date": base.match_date,
        "team": base.home_team, "opponent": base.away_team, "venue": "Neutral",
        "gf": base.home_goals, "ga": base.away_goals,
    })
    away = pd.DataFrame({
        "league": base.league, "season": base.season, "match_date": base.match_date,
        "team": base.away_team, "opponent": base.home_team, "venue": "Neutral",
        "gf": base.away_goals, "ga": base.home_goals,
    })
    frame = pd.concat([home, away], ignore_index=True)
    frame["shots"] = pd.array([pd.NA] * len(frame), dtype="Int32")
    frame["shots_on_target"] = pd.array([pd.NA] * len(frame), dtype="Int32")
    frame["points"] = frame.apply(
        lambda row: 3 if row.gf > row.ga else 1 if row.gf == row.ga else 0, axis=1,
    ).astype("int32")
    return frame


def team_match_factors(matches: pd.DataFrame) -> pd.DataFrame:
    """Expand optional Football-Data match context into one row per team."""
    columns = [
        "league", "season", "match_date", "team", "opponent", "venue",
        "first_half_goals", "second_half_goals", "corners", "fouls",
        "yellow_cards", "red_cards", "referee",
    ]
    if matches.empty:
        return pd.DataFrame(columns=columns)
    data = matches.copy()
    for column in (
        "half_time_home_goals", "half_time_away_goals", "home_corners", "away_corners",
        "home_fouls", "away_fouls", "home_yellows", "away_yellows", "home_reds", "away_reds",
    ):
        if column not in data:
            data[column] = pd.NA
    if "referee" not in data:
        data["referee"] = ""
    home = pd.DataFrame({
        "league": data.league, "season": data.season, "match_date": data.match_date,
        "team": data.home_team, "opponent": data.away_team, "venue": "Home",
        "first_half_goals": data.half_time_home_goals,
        "second_half_goals": data.home_goals - data.half_time_home_goals,
        "corners": data.home_corners, "fouls": data.home_fouls,
        "yellow_cards": data.home_yellows, "red_cards": data.home_reds,
        "referee": data.referee,
    })
    away = pd.DataFrame({
        "league": data.league, "season": data.season, "match_date": data.match_date,
        "team": data.away_team, "opponent": data.home_team, "venue": "Away",
        "first_half_goals": data.half_time_away_goals,
        "second_half_goals": data.away_goals - data.half_time_away_goals,
        "corners": data.away_corners, "fouls": data.away_fouls,
        "yellow_cards": data.away_yellows, "red_cards": data.away_reds,
        "referee": data.referee,
    })
    return pd.concat([home, away], ignore_index=True)[columns]


class AnalysisSystem:
    """Filters, aggregates and compares match rows through one stable interface."""

    def __init__(self, team_matches: pd.DataFrame):
        required = {
            "league", "season", "match_date", "team", "opponent",
            "venue", "gf", "ga", "points",
        }
        missing = required - set(team_matches.columns)
        if missing:
            raise ValueError(f"Analysis input is missing: {', '.join(sorted(missing))}")
        self._matches = team_matches.copy()
        self._matches["match_date"] = pd.to_datetime(self._matches.match_date)

    def build_report(self, request: AnalysisRequest) -> AnalysisReport:
        if request.form_window < 1:
            raise ValueError("form_window must be positive")
        rows = self._matches.copy()
        if request.competitions:
            rows = rows[rows.league.isin(request.competitions)]
        if request.seasons:
            rows = rows[rows.season.isin(request.seasons)]
        if request.teams:
            rows = rows[rows.team.isin(request.teams)]
        if request.venue:
            rows = rows[rows.venue == request.venue]
        rows = rows.sort_values(["team", "season", "match_date"]).reset_index(drop=True)
        if rows.empty:
            return AnalysisReport(rows, pd.DataFrame(), pd.DataFrame(), pd.DataFrame())

        rows["result"] = rows.points.map({3: "W", 1: "D", 0: "L"})
        rankings = rows.groupby(["league", "season", "team"], as_index=False).agg(
            played=("points", "size"), wins=("points", lambda value: int((value == 3).sum())),
            draws=("points", lambda value: int((value == 1).sum())),
            losses=("points", lambda value: int((value == 0).sum())),
            points=("points", "sum"), goals_for=("gf", "sum"),
            goals_against=("ga", "sum"), clean_sheets=("ga", lambda value: int((value == 0).sum())),
        )
        rankings["goal_difference"] = rankings.goals_for - rankings.goals_against
        rankings["points_per_game"] = rankings.points / rankings.played
        rankings["goals_per_game"] = rankings.goals_for / rankings.played
        rankings["conceded_per_game"] = rankings.goals_against / rankings.played
        rankings["win_rate"] = 100 * rankings.wins / rankings.played
        rankings["clean_sheet_rate"] = 100 * rankings.clean_sheets / rankings.played
        rankings = rankings.sort_values(
            ["league", "season", "points", "goal_difference", "goals_for"],
            ascending=[True, True, False, False, False],
        ).reset_index(drop=True)
        rankings["rank"] = rankings.groupby(["league", "season"]).cumcount() + 1

        form = rows.groupby(["league", "season", "team"], group_keys=False).tail(
            request.form_window
        ).groupby(["league", "season", "team"], as_index=False).agg(
            form_matches=("points", "size"), form_points=("points", "sum"),
            form_goals_for=("gf", "sum"), form_goals_against=("ga", "sum"),
            form=("result", lambda value: " ".join(value)),
        )
        form["form_ppg"] = form.form_points / form.form_matches
        rankings = rankings.merge(form, on=["league", "season", "team"], how="left")

        metrics = [
            "points_per_game", "goals_per_game", "conceded_per_game",
            "win_rate", "clean_sheet_rate", "goal_difference", "form_ppg",
        ]
        correlations = rankings[metrics].corr().reset_index(names="metric")
        return AnalysisReport(rows, rankings, form, correlations)
