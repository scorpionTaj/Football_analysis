"""Pipeline status and data-quality coverage."""

from __future__ import annotations

from datetime import datetime

import numpy as np
import pandas as pd

from football_analysis.api.contracts import (
    FixtureCoverageRow,
    PipelineCheck,
    PipelineResponse,
    QualityCell,
    QualityResponse,
)
from football_analysis.api.db import ReadOnlyStore
from football_analysis.config import (
    LEAGUES,
    RECENT_LEAGUES,
    current_season,
    seasons,
)
from football_analysis.fixtures import SOURCE as WEEKLY_FIXTURE_SOURCE
from football_analysis.open_fixtures import SOURCE as FULL_FIXTURE_SOURCE
from football_analysis.api.queries._shared import (
    _as_datetime,
    _has,
    _source,
    _store_source,
)
from football_analysis.api.queries.matches import (
    shot_analysis,
)


def pipeline(store: ReadOnlyStore) -> PipelineResponse:
    """Latest warehouse build: dbt node results, layer sizes and source freshness."""
    if not _has(store, "pipeline_status"):
        return PipelineResponse(source=_source("pipeline", "empty"))
    frame = store.query("SELECT * FROM pipeline_status ORDER BY kind, name")
    checks = [PipelineCheck(
        kind=row.kind, name=row.name, status=row.status,
        value=None if pd.isna(row.value) else float(row.value),
        seconds=None if pd.isna(row.seconds) else float(row.seconds),
        detail=row.detail or "",
    ) for row in frame.itertuples(index=False)]
    tests = [c for c in checks if c.kind == "dbt_test"]
    checked = _as_datetime(frame.checked_at.max()) if not frame.empty else None
    return PipelineResponse(
        checked_at=checked, tests_passed=sum(c.status == "pass" for c in tests),
        tests_failed=sum(c.status in ("fail", "error") for c in tests), checks=checks,
        source=_source("dbt + warehouse", "latest build", checked),
    )


def quality(store: ReadOnlyStore) -> QualityResponse:
    def row_count(table: str) -> int:
        return int(store.scalar(f"SELECT count(*) FROM {table}") or 0) if _has(store, table) else 0

    completed = seasons()
    live = current_season()
    match_count = row_count("mart_dashboard_match")
    recent_count = row_count("recent_matches")
    fixtures = pd.DataFrame()
    if _has(store, "mart_dashboard_match"):
        fixtures = store.query("SELECT league, season, home_shots, away_shots, home_sot, away_sot, home_corners FROM mart_dashboard_match")
    if _has(store, "recent_matches"):
        recent = store.query("SELECT league, season, home_shots, away_shots, home_sot, away_sot, home_corners FROM recent_matches")
        fixtures = pd.concat([fixtures, recent], ignore_index=True) if not recent.empty else fixtures
    impossible = 0
    null_coverage: dict[str, float] = {}
    if not fixtures.empty:
        impossible = int((
            (fixtures.home_sot > fixtures.home_shots) | (fixtures.away_sot > fixtures.away_shots)
        ).fillna(False).sum())
        for column in ("home_shots", "away_shots", "home_sot", "away_sot"):
            null_coverage[column] = float(fixtures[column].isna().mean())
    covered = set()
    live_leagues = set()
    if not fixtures.empty:
        covered = set(zip(fixtures.league, fixtures.season.astype(int)))
        live_leagues = set(fixtures.loc[fixtures.season == live, "league"])
    expected_completed = len(LEAGUES) * len(completed)
    complete_cells = len([1 for league in LEAGUES for year in completed if (league, year) in covered])
    coverage_counts = fixtures.groupby(["league", "season"]).size().to_dict() if not fixtures.empty else {}
    grid = []
    for league in list(LEAGUES) + [code for code in RECENT_LEAGUES if code not in LEAGUES]:
        for year in completed + ([live] if live not in completed else []):
            if (league, year) in covered:
                status = "live_partial" if year == live else "complete"
            else:
                status = "missing"
            grid.append(QualityCell(
                competition=league,
                season=year,
                status=status,
                match_count=int(coverage_counts.get((league, year), 0)),
            ))
    checksums = []
    if _has(store, "ingestion_runs"):
        runs = store.query(
            "SELECT league, season, sha256, status, fetched_at, row_count FROM ingestion_runs "
            "ORDER BY fetched_at DESC LIMIT 25"
        )
        checksums = runs.replace({np.nan: None}).to_dict("records")
    stamps: dict[str, datetime | str | None] = {}
    if _has(store, "analytics_metadata"):
        stamps["analytics"] = _as_datetime(store.scalar("SELECT max(refreshed_at) FROM analytics_metadata"))
    if _has(store, "ingestion_runs"):
        stamps["ingestion"] = _as_datetime(store.scalar("SELECT max(fetched_at) FROM ingestion_runs"))
    if _has(store, "dim_player"):
        stamps["players"] = _as_datetime(store.scalar("SELECT max(fetched_at) FROM dim_player"))
    if _has(store, "fct_match_context"):
        stamps["match_contexts"] = _as_datetime(store.scalar("SELECT max(fetched_at) FROM fct_match_context"))
    if _has(store, "reference_standings"):
        stamps["reference"] = _as_datetime(store.scalar("SELECT max(fetched_at) FROM reference_standings"))
    if _has(store, "recent_matches"):
        stamps["recent"] = _as_datetime(store.scalar("SELECT max(fetched_at) FROM recent_matches"))
    if _has(store, "team_media"):
        stamps["media"] = _as_datetime(store.scalar("SELECT max(fetched_at) FROM team_media"))
    if _has(store, "fct_tournament_match"):
        stamps["tournaments"] = _as_datetime(store.scalar("SELECT max(fetched_at) FROM fct_tournament_match"))
    if _has(store, "event_statistics"):
        stamps["event_details"] = _as_datetime(store.scalar("SELECT max(fetched_at) FROM event_statistics"))
    if _has(store, "prediction_models"):
        stamps["predictions"] = _as_datetime(store.scalar("SELECT max(trained_at) FROM prediction_models"))

    reference_rows = row_count("reference_standings")
    tracked_players = row_count("dim_player")
    player_stat_rows = row_count("fct_player_competition_season")
    artwork_rows = row_count("team_media") + row_count("competition_media")
    tournament_match_count = row_count("fct_tournament_match")
    tournament_goal_count = row_count("fct_tournament_goal")
    event_stat_count = row_count("event_statistics")
    timeline_count = row_count("fct_match_timeline_event")
    lineup_count = row_count("fct_match_lineup")
    prediction_count = row_count("match_predictions")
    fixture_counts = {league: {"full_schedule": 0, "weekly_window": 0, "next_listed": 0, "latest_fetched_at": None}
                      for league in RECENT_LEAGUES}
    if _has(store, "recent_events"):
        event_rows = store.query(
            "SELECT league, source, count(*) AS rows, max(fetched_at) AS fetched_at "
            "FROM recent_events WHERE season=? AND event_kind IN ('fixture', 'next') "
            "AND match_date >= current_date GROUP BY league, source", [live],
        )
        for row in event_rows.itertuples(index=False):
            if row.league not in fixture_counts:
                continue
            field = ("full_schedule" if row.source == FULL_FIXTURE_SOURCE else
                     "weekly_window" if row.source == WEEKLY_FIXTURE_SOURCE else "next_listed")
            fixture_counts[row.league][field] += int(row.rows)
            previous = fixture_counts[row.league]["latest_fetched_at"]
            stamp = _as_datetime(row.fetched_at)
            if stamp is not None and (previous is None or stamp > previous):
                fixture_counts[row.league]["latest_fetched_at"] = stamp
    fixture_coverage = [FixtureCoverageRow(competition=league, **counts)
                        for league, counts in fixture_counts.items()]
    recent_competitions = int(fixtures.loc[fixtures.season == live, "league"].nunique()) if not fixtures.empty else 0
    player_clubs = int(store.scalar("SELECT count(DISTINCT team) FROM dim_player") or 0) if _has(store, "dim_player") else 0
    tournament_teams = 0
    tournament_breakdown: dict[str, int] = {}
    if _has(store, "fct_tournament_match"):
        tournament_teams = int(store.scalar(
            "SELECT count(DISTINCT team) FROM (SELECT home_team AS team FROM fct_tournament_match UNION SELECT away_team FROM fct_tournament_match)"
        ) or 0)
        breakdown = store.query("SELECT competition, count(*) AS matches FROM fct_tournament_match GROUP BY competition")
        tournament_breakdown = {str(row.competition): int(row.matches) for row in breakdown.itertuples(index=False)}
    context_rich = int(fixtures.home_corners.notna().sum()) if not fixtures.empty and "home_corners" in fixtures else 0
    match_context_rows = row_count("fct_match_context")
    formation_rows = int(store.scalar(
        "SELECT count(*) FROM fct_match_context WHERE home_formation <> '' OR away_formation <> ''"
    ) or 0) if _has(store, "fct_match_context") else 0
    coach_rows = int(store.scalar(
        "SELECT count(*) FROM fct_match_context WHERE home_coach <> '' OR away_coach <> ''"
    ) or 0) if _has(store, "fct_match_context") else 0
    shots = shot_analysis(store)
    caps = [
        "TheSportsDB free standings and player feeds are explicitly capped.",
        "Transfermarkt Open Dataset is a 2025/26 snapshot with no 2026/27 squad rows.",
        "OpenFootball supplies verified full-season schedules for eight leagues (Greece: regular season); Belgium joins once every round is dated, and Turkey still relies on shorter feeds.",
        "Future fixture dates and source-local kickoff times are provisional until the publishers update them.",
    ]
    return QualityResponse(
        completed_coverage=f"{complete_cells}/{expected_completed}",
        live_competitions=f"{len(live_leagues)}/{len(RECENT_LEAGUES)}",
        match_records=match_count + recent_count,
        impossible_shot_rows=impossible,
        reference_rows=reference_rows,
        recent_competitions=recent_competitions,
        completed_results=recent_count,
        tracked_players=tracked_players,
        player_clubs=player_clubs,
        player_stat_rows=player_stat_rows,
        artwork_rows=artwork_rows,
        tournament_matches=tournament_match_count,
        tournament_teams=tournament_teams,
        tournament_breakdown=tournament_breakdown,
        context_rich_matches=context_rich,
        match_context_rows=match_context_rows,
        formation_rows=formation_rows,
        coach_rows=coach_rows,
        tournament_goals=tournament_goal_count,
        detailed_event_stats=event_stat_count,
        timeline_events=timeline_count,
        lineup_rows=lineup_count,
        model_predictions=prediction_count,
        fixture_coverage=fixture_coverage,
        source_caps=caps,
        null_coverage=null_coverage,
        checksums=checksums,
        refresh_timestamps=stamps,
        grid=grid,
        shot_coverage=shots.coverage,
        source=_source(_store_source(store), "quality"),
    )
