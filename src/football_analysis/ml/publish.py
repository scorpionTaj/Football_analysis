"""Write the champion into the app's prediction tables (prediction_models, match_predictions,
forecast_history) so the existing /api/v1/predictions contract keeps working."""

from __future__ import annotations

import json
import math
from datetime import datetime

import numpy as np
import pandas as pd

from ..teams import team_key
from .evaluate import metrics as proper_metrics

CLASS_NAMES = np.array(["Home", "Draw", "Away"])
HIGH_CONFIDENCE_THRESHOLD = 0.75


def _metrics(probabilities, labels, baseline_prevalence=None):
    actual = np.asarray(labels, dtype=int)
    clipped = np.clip(probabilities, 1e-9, 1)
    predicted = probabilities.argmax(axis=1)
    prevalence = (
        np.bincount(actual, minlength=3) / len(actual)
        if baseline_prevalence is None else np.asarray(baseline_prevalence, dtype=float)
    )
    baseline = np.tile(prevalence, (len(actual), 1))
    return {
        "accuracy": float((predicted == actual).mean()),
        "log_loss": float(-np.log(clipped[np.arange(len(actual)), actual]).mean()),
        "brier_score": float(np.square(probabilities - np.eye(3)[actual]).sum(axis=1).mean()),
        "baseline_accuracy": float((np.full(len(actual), prevalence.argmax()) == actual).mean()),
        "baseline_log_loss": float(-np.log(np.clip(baseline[np.arange(len(actual)), actual], 1e-9, 1)).mean()),
    }


def _confidence_backtest(probabilities, labels, threshold=HIGH_CONFIDENCE_THRESHOLD):
    """Report selective accuracy and uncertainty without hiding excluded games."""
    actual = np.asarray(labels, dtype=int)
    selected = probabilities.max(axis=1) >= threshold
    count = int(selected.sum())
    correct = int((probabilities[selected].argmax(axis=1) == actual[selected]).sum()) if count else 0
    observed = correct / count if count else None
    if count:
        z = 1.96
        centre = (observed + z * z / (2 * count)) / (1 + z * z / count)
        margin = z * math.sqrt(
            observed * (1 - observed) / count + z * z / (4 * count * count)
        ) / (1 + z * z / count)
        lower, upper = max(0.0, centre - margin), min(1.0, centre + margin)
    else:
        lower = upper = None
    return {
        "high_confidence_threshold": threshold,
        "high_confidence_matches": count,
        "high_confidence_coverage": count / len(actual),
        "high_confidence_accuracy": observed,
        "high_confidence_low95": lower,
        "high_confidence_high95": upper,
    }


def _outcome_backtest(probabilities, labels):
    """Expose class imbalance and missed draws instead of one accuracy number."""
    actual = np.asarray(labels, dtype=int)
    predicted = probabilities.argmax(axis=1)
    rows = []
    for index, outcome in enumerate(CLASS_NAMES):
        actual_count = int((actual == index).sum())
        predicted_count = int((predicted == index).sum())
        correct = int(((actual == index) & (predicted == index)).sum())
        rows.append({
            "outcome": str(outcome), "matches": actual_count,
            "predicted": predicted_count, "correct": correct,
            "recall": correct / actual_count if actual_count else None,
            "precision": correct / predicted_count if predicted_count else None,
        })
    return rows


def _reconcile_forecast_history(con, matches):
    """Resolve published probabilities against completed results without rewriting them."""
    pending = con.sql("SELECT model_id, league, season, match_date, home_team, away_team "
                      "FROM forecast_history WHERE actual_result IS NULL").df()
    if pending.empty:
        return
    results = {}
    for row in matches.itertuples(index=False):
        if pd.isna(row.home_goals) or pd.isna(row.away_goals):
            continue
        key = (row.league, int(row.season), team_key(row.home_team), team_key(row.away_team))
        results[key] = "Home" if row.home_goals > row.away_goals else "Away" if row.home_goals < row.away_goals else "Draw"
    for row in pending.itertuples(index=False):
        key = (row.league, int(row.season), team_key(row.home_team), team_key(row.away_team))
        actual = results.get(key)
        if actual:
            con.execute(
                "UPDATE forecast_history SET actual_result=?, resolved_at=current_timestamp "
                "WHERE model_id=? AND league=? AND match_date=? AND home_team=? AND away_team=?",
                [actual, row.model_id, row.league, row.match_date, row.home_team, row.away_team],
            )


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
        # Journal a forecast only when it is new or moved by at least one percentage point;
        # retraining on unchanged inputs must not grow the journal.
        con.execute("""
            INSERT OR IGNORE INTO forecast_history
            SELECT h.* FROM incoming_history h
            WHERE NOT EXISTS (
                SELECT 1 FROM forecast_history f
                WHERE f.actual_result IS NULL AND f.league = h.league AND f.season = h.season
                  AND f.match_date = h.match_date AND f.home_team = h.home_team AND f.away_team = h.away_team
                  AND abs(f.home_probability - h.home_probability) < 0.01
                  AND abs(f.away_probability - h.away_probability) < 0.01)""")
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
