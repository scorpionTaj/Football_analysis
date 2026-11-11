"""The analysis report, league standings and tournaments."""

from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd

from football_analysis.analysis_system import (
    AnalysisRequest,
    AnalysisSystem,
    team_match_factors,
    tournament_team_matches,
)
from football_analysis.api.contracts import (
    AnalysisFilters,
    AnalysisReportResponse,
    CorrelationRow,
    EloRatingRow,
    FormRow,
    MatchFactorSummary,
    RankingRow,
    ReferenceStandingRow,
    RefereeSummary,
    StandingsResponse,
    TournamentGoal,
    TournamentMatch,
    TournamentResponse,
    TournamentStage,
)
from football_analysis.api.db import ReadOnlyStore
from football_analysis.config import (
    COMPETITIONS,
    TOURNAMENTS,
)
from football_analysis.teams import team_key
from football_analysis.api.queries._shared import (
    _as_date,
    _as_datetime,
    _build_team_ref,
    _has,
    _mean,
    _source,
    _team_media_map,
)


def _load_analysis_matches(store: ReadOnlyStore) -> pd.DataFrame:
    parts = []
    if _has(store, "mart_dashboard_team_match"):
        parts.append(store.query("SELECT * FROM mart_dashboard_team_match"))
    if _has(store, "recent_matches"):
        recent = store.query(
            "SELECT league, season, match_date, home_team, away_team, home_goals, away_goals, "
            "home_shots, away_shots, home_sot, away_sot FROM recent_matches"
        )
        if not recent.empty:
            home = pd.DataFrame({
                "league": recent.league, "season": recent.season, "match_date": recent.match_date,
                "team": recent.home_team, "opponent": recent.away_team, "venue": "Home",
                "gf": recent.home_goals, "ga": recent.away_goals,
                "shots": recent.home_shots, "shots_on_target": recent.home_sot,
            })
            away = pd.DataFrame({
                "league": recent.league, "season": recent.season, "match_date": recent.match_date,
                "team": recent.away_team, "opponent": recent.home_team, "venue": "Away",
                "gf": recent.away_goals, "ga": recent.home_goals,
                "shots": recent.away_shots, "shots_on_target": recent.away_sot,
            })
            expanded = pd.concat([home, away], ignore_index=True)
            expanded["points"] = np.where(
                expanded.gf > expanded.ga, 3, np.where(expanded.gf == expanded.ga, 1, 0)
            )
            parts.append(expanded)
    if _has(store, "fct_tournament_match"):
        tourney = store.query("SELECT * FROM fct_tournament_match")
        if not tourney.empty:
            parts.append(tournament_team_matches(tourney))
    if not parts:
        return pd.DataFrame(columns=[
            "league", "season", "match_date", "team", "opponent", "venue", "gf", "ga", "points",
        ])
    frame = pd.concat(parts, ignore_index=True)
    return frame.drop_duplicates(["league", "season", "match_date", "team", "opponent", "venue"])


def _resolve_teams(frame: pd.DataFrame, requested: list[str]) -> list[str]:
    if not requested:
        return []
    keys = {team_key(name) or name: name for name in frame.team.unique()}
    resolved = []
    for value in requested:
        key = team_key(value) or value
        if value in set(frame.team):
            resolved.append(value)
        elif key in keys:
            resolved.append(keys[key])
        else:
            resolved.append(value)
    return resolved


def _factor_summary(store: ReadOnlyStore, filters: AnalysisFilters) -> MatchFactorSummary:
    if not _has(store, "mart_dashboard_match"):
        return MatchFactorSummary()
    fixtures = store.query("SELECT * FROM mart_dashboard_match")
    if _has(store, "recent_matches"):
        recent = store.query("SELECT * FROM recent_matches")
        if not recent.empty:
            fixtures = pd.concat([fixtures, recent], ignore_index=True)
    if fixtures.empty:
        return MatchFactorSummary()
    if filters.competitions:
        fixtures = fixtures[fixtures.league.isin(filters.competitions)]
    if filters.seasons:
        fixtures = fixtures[fixtures.season.isin(filters.seasons)]
    factors = team_match_factors(fixtures)
    if filters.teams:
        wanted = {team_key(name) or name for name in filters.teams}
        factors = factors[factors.team.map(team_key).isin(wanted) | factors.team.isin(filters.teams)]
    if filters.venue:
        factors = factors[factors.venue == filters.venue]
    if factors.empty:
        return MatchFactorSummary()
    referees = []
    named = factors[factors.referee.fillna("") != ""]
    if not named.empty:
        grouped = named.groupby("referee", as_index=False).agg(
            matches=("referee", "size"),
            yellow_cards_mean=("yellow_cards", "mean"),
            red_cards_mean=("red_cards", "mean"),
        ).sort_values("matches", ascending=False).head(8)
        referees = [
            RefereeSummary(
                referee=row.referee,
                matches=int(row.matches),
                yellow_cards_mean=None if pd.isna(row.yellow_cards_mean) else float(row.yellow_cards_mean),
                red_cards_mean=None if pd.isna(row.red_cards_mean) else float(row.red_cards_mean),
            )
            for row in grouped.itertuples(index=False)
        ]
    return MatchFactorSummary(
        first_half_goals_mean=_mean(factors.first_half_goals),
        second_half_goals_mean=_mean(factors.second_half_goals),
        corners_mean=_mean(factors.corners),
        fouls_mean=_mean(factors.fouls),
        yellow_cards_mean=_mean(factors.yellow_cards),
        red_cards_mean=_mean(factors.red_cards),
        referees=referees,
    )


def build_analysis(store: ReadOnlyStore, body: AnalysisFilters) -> AnalysisReportResponse:
    tm_map = _team_media_map(store)
    matches = _load_analysis_matches(store)
    teams = _resolve_teams(matches, body.teams)
    request = AnalysisRequest(
        competitions=tuple(body.competitions),
        seasons=tuple(body.seasons),
        teams=tuple(teams),
        venue=body.venue,
        form_window=body.form_window,
    )
    report = AnalysisSystem(matches).build_report(request) if not matches.empty else AnalysisSystem(
        pd.DataFrame(columns=[
            "league", "season", "match_date", "team", "opponent", "venue", "gf", "ga", "points",
        ])
    ).build_report(request)
    rankings = []
    for row in report.rankings.itertuples(index=False):
        rankings.append(RankingRow(
            competition=row.league, season=int(row.season), team=_build_team_ref(row.team, tm_map),
            rank=int(row.rank), played=int(row.played), wins=int(row.wins), draws=int(row.draws),
            losses=int(row.losses), points=int(row.points), goals_for=int(row.goals_for),
            goals_against=int(row.goals_against), goal_difference=int(row.goal_difference),
            points_per_game=float(row.points_per_game), goals_per_game=float(row.goals_per_game),
            conceded_per_game=float(row.conceded_per_game), win_rate=float(row.win_rate),
            clean_sheet_rate=float(row.clean_sheet_rate),
            form=None if pd.isna(getattr(row, "form", None)) else str(row.form),
            form_ppg=None if pd.isna(getattr(row, "form_ppg", None)) else float(row.form_ppg),
        ))
    form = [
        FormRow(
            competition=row.league, season=int(row.season), team=_build_team_ref(row.team, tm_map),
            form_matches=int(row.form_matches), form_points=int(row.form_points),
            form_goals_for=int(row.form_goals_for), form_goals_against=int(row.form_goals_against),
            form=str(row.form), form_ppg=float(row.form_ppg),
        )
        for row in report.form.itertuples(index=False)
    ]
    correlations = []
    if not report.correlations.empty:
        for record in report.correlations.replace({np.nan: None}).to_dict("records"):
            correlations.append(CorrelationRow.model_validate(record))

    elo_ratings = []
    if _has(store, "elo_ratings"):
        elo_sql = "SELECT league, season, match_date, team, opponent, venue, post_elo FROM elo_ratings"
        clauses = []
        params = []
        if body.competitions:
            placeholders = ", ".join("?" for _ in body.competitions)
            clauses.append(f"league IN ({placeholders})")
            params.extend(body.competitions)
        if body.seasons:
            placeholders = ", ".join("?" for _ in body.seasons)
            clauses.append(f"season IN ({placeholders})")
            params.extend(body.seasons)
        if body.teams:
            resolved_teams = _resolve_teams(matches, body.teams) if not matches.empty else body.teams
            placeholders = ", ".join("?" for _ in resolved_teams)
            clauses.append(f"team IN ({placeholders})")
            params.extend(resolved_teams)
        if clauses:
            elo_sql += " WHERE " + " AND ".join(clauses)
        elo_df = store.query(elo_sql, params)
        if not elo_df.empty:
            elo_df = elo_df.sort_values(
                ["match_date", "league", "season", "team", "opponent", "venue"],
                ascending=[False, True, True, True, True, True], kind="stable",
            )
            latest_elo = elo_df.drop_duplicates(subset=["league", "season", "team"], keep="first")
            for erow in latest_elo.itertuples(index=False):
                elo_ratings.append(EloRatingRow(
                    team=_build_team_ref(erow.team, tm_map),
                    season=int(erow.season),
                    league=erow.league,
                    post_elo=round(float(erow.post_elo), 1),
                ))

    return AnalysisReportResponse(
        filters=body,
        match_count=int(len(report.matches)),
        rankings=rankings,
        form=form,
        correlations=correlations,
        match_factors=_factor_summary(store, body),
        elo_ratings=elo_ratings,
        source=_source("analysis-system", "rankings+form+correlations+elo"),
    )


def standings(
    store: ReadOnlyStore,
    competition: str,
    season: int,
    form_window: int = 5,
    venue: str | None = None,
) -> StandingsResponse:
    """Return the results-derived table and the optional external validation table."""
    report = build_analysis(store, AnalysisFilters(
        competitions=[competition], seasons=[season], form_window=form_window, venue=venue,
    ))
    derived = {team_key(row.team.name): row for row in report.rankings}
    reference_rows: list[ReferenceStandingRow] = []
    freshness = None
    if _has(store, "reference_standings"):
        frame = store.query(
            "SELECT * FROM reference_standings WHERE league = ? AND season = ? ORDER BY rank",
            [competition, season],
        )
        if not frame.empty:
            freshness = frame.fetched_at.max()
        media = _team_media_map(store)
        for row in frame.itertuples(index=False):
            result = derived.get(team_key(row.team))
            ref_points = None if pd.isna(row.points) else int(row.points)
            result_points = result.points if result else None
            ref_rank = int(row.rank)
            result_rank = result.rank if result else None
            reference_rows.append(ReferenceStandingRow(
                competition=competition,
                season=season,
                source_name=row.source,
                rank=ref_rank,
                team=_build_team_ref(row.team, media),
                played=None if pd.isna(row.played) else int(row.played),
                points=ref_points,
                goal_difference=None if pd.isna(row.goal_difference) else int(row.goal_difference),
                form=None if pd.isna(row.form) else str(row.form),
                description=None if pd.isna(row.description) else str(row.description),
                source_updated_at=_as_datetime(row.source_updated_at),
                fetched_at=_as_datetime(row.fetched_at),
                results_rank=result_rank,
                results_points=result_points,
                results_goal_difference=result.goal_difference if result else None,
                point_adjustment=(ref_points - result_points) if ref_points is not None and result_points is not None else None,
                rank_difference=(ref_rank - result_rank) if result_rank is not None else None,
            ))
    return StandingsResponse(
        competition=competition,
        season=season,
        rankings=report.rankings,
        reference=reference_rows,
        source=_source("analysis-system+reference", "results-derived and external validation", freshness),
    )


def tournament(store: ReadOnlyStore, competition: str, season: int) -> TournamentResponse:
    name = TOURNAMENTS.get(competition, COMPETITIONS.get(competition, competition))
    if not _has(store, "fct_tournament_match"):
        return TournamentResponse(
            competition=competition, name=name, season=season,
            stages=[], matches=[], scorers=[],
            source=_source("openfootball", "empty"),
        )
    matches = store.query(
        "SELECT * FROM fct_tournament_match WHERE competition = ? AND season = ?",
        [competition, season],
    )
    matches = matches.sort_values(["match_date", "home_team", "away_team"], kind="stable")
    stages = []
    if not matches.empty:
        grouped = matches.groupby("stage", as_index=False).size().rename(columns={"size": "match_count"})
        stages = [TournamentStage(stage=row.stage, match_count=int(row.match_count)) for row in grouped.itertuples(index=False)]
    tm_map = _team_media_map(store)
    payload = []
    for row in matches.itertuples(index=False):
        payload.append(TournamentMatch(
            competition=row.competition, season=int(row.season),
            match_date=_as_date(row.match_date) or date.min,
            home=_build_team_ref(row.home_team, tm_map), away=_build_team_ref(row.away_team, tm_map),
            home_goals=int(row.home_goals), away_goals=int(row.away_goals),
            venue=row.venue, stage=row.stage, source=row.source,
            group_name=None if pd.isna(row.group_name) else row.group_name,
            home_penalties=None if pd.isna(row.home_penalties) else int(row.home_penalties),
            away_penalties=None if pd.isna(row.away_penalties) else int(row.away_penalties),
            status=row.status,
        ))
    scorers = []
    if _has(store, "fct_tournament_goal"):
        goals = store.query(
            "SELECT * FROM fct_tournament_goal WHERE competition = ? AND season = ?",
            [competition, season],
        )
        goals = goals.sort_values(["match_date", "player", "team", "minute"], kind="stable")
        scorers = [
            TournamentGoal(
                match_date=_as_date(row.match_date) or date.min,
                team=_build_team_ref(row.team, tm_map), player=row.player,
                minute=None if pd.isna(row.minute) else str(row.minute),
                penalty=bool(row.penalty), own_goal=bool(row.own_goal),
            )
            for row in goals.itertuples(index=False)
        ]
    freshness = None if matches.empty else matches.fetched_at.max()
    source_names = sorted({str(value) for value in matches.source.dropna() if str(value).strip()}) if not matches.empty else []
    return TournamentResponse(
        competition=competition, name=name, season=season,
        stages=stages, matches=payload, scorers=scorers,
        source=_source(" + ".join(source_names) or "configured tournament sources", "tournament", freshness),
    )
