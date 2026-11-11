"""Match forecasts, title outlooks and model runs."""

from __future__ import annotations

import json
from datetime import date, datetime
from typing import Any

import numpy as np
import pandas as pd

from football_analysis.api.contracts import (
    CalibrationBin,
    Forecast,
    ForecastAuditRow,
    LeagueTitleOutlook,
    ModelRun,
    ModelsResponse,
    PredictionsResponse,
    Team,
)
from football_analysis.api.db import ReadOnlyStore
from football_analysis.config import (
    RECENT_LEAGUES,
    current_season,
)
from football_analysis.api.queries._shared import (
    _as_date,
    _as_datetime,
    _build_team_ref,
    _has,
    _present,
    _source,
    _team_media_map,
)
from football_analysis.api.queries.reference import (
    list_teams,
)


def _calibration(validation: pd.DataFrame) -> list[CalibrationBin]:
    if validation.empty or "actual_result" not in validation:
        return []
    bins = []
    for column, outcome in (
        ("home_probability", "Home"),
        ("draw_probability", "Draw"),
        ("away_probability", "Away"),
    ):
        observed = (validation.actual_result == outcome).astype(float)
        bins.append(CalibrationBin(
            predicted_outcome=outcome,
            mean_probability=float(validation[column].mean()),
            observed_rate=float(observed.mean()),
            samples=int(len(validation)),
        ))
    return bins


def _league_title_outlooks(store: ReadOnlyStore, tm_map: dict[str, Any]) -> list[LeagueTitleOutlook]:
    """Project title shares from current points with conservative early-season smoothing."""
    live = current_season()
    grouped: dict[str, list[Team]] = {}
    for team in list_teams(store, None, live).teams:
        if team.competition in RECENT_LEAGUES:
            grouped.setdefault(team.competition, []).append(team)

    outlooks: list[LeagueTitleOutlook] = []
    for competition, teams in grouped.items():
        if len(teams) < 2:
            continue
        ranked = sorted(teams, key=lambda item: (-item.points, -item.played, item.name))
        season_matches = 2 * (len(teams) - 1)
        projections = []
        for rank, team in enumerate(ranked, 1):
            remaining = max(0, season_matches - team.played)
            smoothed_ppg = (team.points + 5 * 1.35) / (team.played + 5)
            projections.append((rank, team, team.points + remaining * smoothed_ppg, remaining))
        best = max(row[2] for row in projections)
        uncertainty = max(2.5, 1.6 * np.sqrt(max(row[3] for row in projections)))
        weights = np.exp(np.array([(row[2] - best) / uncertainty for row in projections]))
        weights /= weights.sum()
        for (rank, team, projected, _), probability in zip(projections, weights):
            outlooks.append(LeagueTitleOutlook(
                competition=competition,
                season=live,
                team=_build_team_ref(team.name, tm_map),
                current_rank=rank,
                played=team.played,
                points=team.points,
                projected_points=round(float(projected), 1),
                title_probability=round(float(probability), 4),
            ))
    return outlooks


# Live score of the journal: each match's last forecast issued before it was resolved, scored with
# the ranked probability score (same metric as the walk-forward leaderboard). Portable SQL: it runs
# on DuckDB, PostgreSQL and the SQLite fallback.
LIVE_FORECAST_SQL = """
WITH final AS (
    SELECT home_probability AS ph, draw_probability AS pd, actual_result,
           row_number() OVER (PARTITION BY league, match_date, home_team, away_team ORDER BY issued_at DESC) AS rn
    FROM forecast_history WHERE actual_result IS NOT NULL
), scored AS (
    SELECT ph - CASE WHEN actual_result = 'Home' THEN 1 ELSE 0 END AS c1,
           ph + pd - CASE WHEN actual_result = 'Away' THEN 0 ELSE 1 END AS c2
    FROM final WHERE rn = 1
)
SELECT count(*) AS matches, avg((c1 * c1 + c2 * c2) / 2) AS rps FROM scored
"""


def predictions(store: ReadOnlyStore) -> PredictionsResponse:
    empty = PredictionsResponse(source=_source("champion-model", "empty"))
    if not _has(store, "prediction_models"):
        return empty
    models = store.query("SELECT * FROM prediction_models ORDER BY trained_at DESC, model_id LIMIT 1")
    if models.empty:
        return empty
    model = models.iloc[0]
    metrics = json.loads(model.metrics) if isinstance(model.metrics, str) else (model.metrics or {})
    forecasts = []
    forecast_history = []
    forecast_record = {}
    calibration: list[CalibrationBin] = []
    tm_map = _team_media_map(store)
    if _has(store, "match_predictions"):
        rows = store.query(
            "SELECT * FROM match_predictions WHERE model_id = ?", [model.model_id]
        )
        rows = rows.sort_values(
            ["league", "season", "match_date", "home_team", "away_team", "prediction_kind"], kind="stable",
        )
        future = rows[rows.prediction_kind == "forecast"] if not rows.empty else rows
        for row in future.itertuples(index=False):
            forecasts.append(Forecast(
                competition=row.league, season=int(row.season),
                match_date=_as_date(row.match_date) or date.min,
                home=_build_team_ref(row.home_team, tm_map), away=_build_team_ref(row.away_team, tm_map),
                predicted_result=row.predicted_result,
                home_probability=float(row.home_probability),
                draw_probability=float(row.draw_probability),
                away_probability=float(row.away_probability),
            ))
        validation = rows[rows.prediction_kind == "validation"] if not rows.empty else rows
        calibration = _calibration(validation)
    if _has(store, "forecast_history"):
        record = store.query(
            "SELECT count(*) AS issued, count(actual_result) AS resolved, "
            "sum(CASE WHEN actual_result=predicted_result THEN 1 ELSE 0 END) AS correct "
            "FROM forecast_history"
        ).iloc[0]
        resolved = int(record.resolved or 0)
        correct = int(record.correct) if pd.notna(record.correct) else 0
        live = store.query(LIVE_FORECAST_SQL).iloc[0]
        forecast_record = {
            "issued": int(record.issued or 0), "resolved": resolved,
            "correct": correct,
            "accuracy": correct / resolved if resolved else None,
            "matches_scored": int(live.matches or 0),
            "rps": None if pd.isna(live.rps) else float(live.rps),
            "walk_forward_rps": metrics.get("rps"),
        }
        history = store.query("SELECT * FROM forecast_history")
        history = history.sort_values(
            ["issued_at", "match_date", "league", "home_team", "away_team", "model_id"],
            ascending=[False, True, True, True, True, True], kind="stable",
        ).head(30)
        for row in history.itertuples(index=False):
            forecast_history.append(ForecastAuditRow(
                model_id=row.model_id, competition=row.league, season=int(row.season),
                match_date=_as_date(row.match_date) or date.min,
                home=_build_team_ref(row.home_team, tm_map),
                away=_build_team_ref(row.away_team, tm_map),
                predicted_result=row.predicted_result,
                home_probability=float(row.home_probability),
                draw_probability=float(row.draw_probability),
                away_probability=float(row.away_probability),
                issued_at=_as_datetime(row.issued_at) or datetime.min,
                actual_result=_present(row.actual_result),
                resolved_at=_as_datetime(row.resolved_at),
            ))
    return PredictionsResponse(
        model_id=model.model_id, model_name=model.model_name,
        trained_at=_as_datetime(model.trained_at),
        validation_cutoff=_as_date(model.validation_cutoff),
        metrics=metrics, calibration=calibration, forecasts=forecasts,
        forecast_history=forecast_history, forecast_record=forecast_record,
        league_outlooks=_league_title_outlooks(store, tm_map),
        source=_source("champion-model", "predictions", model.trained_at),
    )


def models(store: ReadOnlyStore) -> ModelsResponse:
    """Walk-forward leaderboard of every candidate model (written by football-train-models)."""
    from football_analysis.ml import TARGETS

    if not _has(store, "model_runs"):
        return ModelsResponse(targets=TARGETS, source=_source("model-leaderboard", "empty"))
    frame = store.query("SELECT * FROM model_runs ORDER BY rps")

    def parsed(value):
        return json.loads(value) if isinstance(value, str) and value else []

    runs = [ModelRun(
        model=row.model, log_loss=float(row.log_loss), rps=float(row.rps), brier=float(row.brier),
        accuracy=float(row.accuracy), ece=float(row.ece), matches=int(row.n),
        independent=bool(row.independent), is_champion=bool(row.is_champion),
        trained_at=_as_datetime(row.trained_at),
        params=parsed(getattr(row, "params", None)) or {},
        seasons=parsed(getattr(row, "seasons", None)), calibration=parsed(row.bins),
    ) for row in frame.itertuples(index=False)]
    champion = next((run.model for run in runs if run.is_champion), None)
    trained = runs[0].trained_at if runs else None
    return ModelsResponse(champion=champion, targets=TARGETS, runs=runs,
                          source=_source("model-leaderboard", "walk-forward", trained))
