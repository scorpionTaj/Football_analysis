"""Write the champion into the app's prediction tables (prediction_models, match_predictions,
forecast_history) so the existing /api/v1/predictions contract keeps working."""

from __future__ import annotations

import json
from datetime import datetime

import numpy as np
import pandas as pd

from ..predictions import (
    CLASS_NAMES, _confidence_backtest, _metrics, _outcome_backtest, _reconcile_forecast_history,
)
from .evaluate import metrics as proper_metrics

LABELS = dict(enumerate(CLASS_NAMES))
PROBS = ["p_home", "p_draw", "p_away"]


def champion_metrics(oos: pd.DataFrame, champion: str, board: pd.DataFrame, train_matches: int) -> dict:
    mine = oos[oos.model == champion]
    baseline = oos[oos.model == "prevalence_baseline"]
    p, y = mine[PROBS].to_numpy(), mine.outcome.to_numpy()
    walk_forward = []
    for season, part in mine.groupby("season"):
        base = baseline[baseline.season == season]
        walk_forward.append({
            "season": int(season), "matches": len(part),
            **{k: v for k, v in _metrics(part[PROBS].to_numpy(), part.outcome.to_numpy()).items()
               if k in ("accuracy", "log_loss")},
            "baseline_accuracy": float((base[PROBS].to_numpy().argmax(1) == base.outcome.to_numpy()).mean()),
            "rps": proper_metrics(part[PROBS].to_numpy(), part.outcome.to_numpy())["rps"],
        })
    leagues = [{"league": league, "matches": len(part),
                **{k: v for k, v in _metrics(part[PROBS].to_numpy(), part.outcome.to_numpy()).items()
                   if k in ("accuracy", "log_loss")}}
               for league, part in mine.groupby("league")]
    market = board.set_index("model").loc["market_closing"]
    return {
        **_metrics(p, y, np.bincount(y, minlength=3) / len(y)),
        **{k: v for k, v in proper_metrics(p, y).items() if k in ("rps", "ece")},
        **_confidence_backtest(p, y),
        "outcome_backtest": _outcome_backtest(p, y),
        "walk_forward": walk_forward,
        "league_backtest": sorted(leagues, key=lambda r: r["league"]),
        "validation_matches": int(len(mine)),
        "train_matches": int(train_matches),
        "market_log_loss": float(market.log_loss),
        "market_rps": float(market.rps),
        "feature_count": None,
        "leaderboard": board[["model", "log_loss", "rps", "brier", "accuracy", "ece", "independent", "is_champion"]]
        .to_dict(orient="records"),
    }


def publish_to_app(con, champion, board, oos, current, played, train_matches, feature_count):
    stamp = datetime.now().replace(microsecond=0)
    model_id = f"{champion}-{stamp:%Y%m%d%H%M%S}"
    metrics = champion_metrics(oos, champion, board, train_matches)
    metrics["feature_count"] = feature_count
    keys = ["league", "season", "match_date", "home_team", "away_team"]

    validation = oos[oos.model == champion][[*keys, "outcome", *PROBS]].rename(columns=dict(zip(
        PROBS, ["home_probability", "draw_probability", "away_probability"])))
    validation["actual_result"] = validation.outcome.map(LABELS)
    validation["prediction_kind"] = "validation"
    forecasts = current[current.is_fixture][[*keys, "home_probability", "draw_probability", "away_probability"]].copy()
    forecasts["actual_result"] = None
    forecasts["prediction_kind"] = "forecast"
    rows = pd.concat([validation, forecasts], ignore_index=True)
    probs = rows[["home_probability", "draw_probability", "away_probability"]].to_numpy()
    rows["predicted_result"] = CLASS_NAMES[probs.argmax(1)]
    rows["model_id"] = model_id
    rows["match_date"] = pd.to_datetime(rows.match_date).dt.date
    rows = rows[["model_id", "prediction_kind", *keys, "actual_result", "predicted_result",
                 "home_probability", "draw_probability", "away_probability"]]

    history = rows[rows.prediction_kind == "forecast"].drop(columns=["prediction_kind", "actual_result"]).assign(
        issued_at=stamp, actual_result=None, resolved_at=None)
    history = history[["model_id", *keys, "predicted_result", "home_probability", "draw_probability",
                       "away_probability", "issued_at", "actual_result", "resolved_at"]]
    model_row = pd.DataFrame([{
        "model_id": model_id, "model_name": f"Champion · {champion.replace('_', ' ')} (walk-forward RPS)",
        "trained_at": stamp, "validation_cutoff": pd.to_datetime(validation.match_date).min().date(),
        "train_matches": int(train_matches), "validation_matches": int(len(validation)),
        "feature_names": json.dumps(feature_count), "parameters": json.dumps({"champion": champion}),
        "metrics": json.dumps(metrics, default=float),
    }])

    _reconcile_forecast_history(con, played)
    con.register("incoming_model", model_row)
    con.register("incoming_predictions", rows)
    con.register("incoming_history", history)
    con.execute("BEGIN")
    try:
        con.execute("INSERT OR IGNORE INTO forecast_history SELECT * FROM incoming_history")
        con.execute("DELETE FROM match_predictions")
        con.execute("DELETE FROM prediction_models")
        con.execute("INSERT INTO prediction_models SELECT * FROM incoming_model")
        con.execute("INSERT INTO match_predictions SELECT * FROM incoming_predictions")
        con.execute("COMMIT")
    except Exception:
        con.execute("ROLLBACK")
        raise
    finally:
        for name in ("incoming_model", "incoming_predictions", "incoming_history"):
            con.unregister(name)
    return {"model_id": model_id, "forecasts": int(len(forecasts)), "validation": int(len(validation))}
