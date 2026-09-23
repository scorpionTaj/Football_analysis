"""Leakage-aware football result probabilities using a compact softmax model."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

from .config import DB
from .ingest import connect
from .prediction_features import FEATURES, build_match_features, future_features, load_match_inputs
from .teams import team_key

MODEL_VERSION = "softmax-form-shots-v4"
HIGH_CONFIDENCE_THRESHOLD = 0.75
CLASS_NAMES = np.array(["Home", "Draw", "Away"])


@dataclass(frozen=True)
class SoftmaxModel:
    mean: np.ndarray
    scale: np.ndarray
    weights: np.ndarray
    temperature: float = 1.0

    def predict_proba(self, features):
        values = (np.asarray(features, dtype=float) - self.mean) / self.scale
        logits = (np.c_[np.ones(len(values)), values] @ self.weights) / self.temperature
        logits -= logits.max(axis=1, keepdims=True)
        probabilities = np.exp(logits)
        return probabilities / probabilities.sum(axis=1, keepdims=True)

    def to_json(self):
        return json.dumps({
            "mean": self.mean.tolist(), "scale": self.scale.tolist(),
            "weights": self.weights.tolist(), "temperature": self.temperature,
        })


def fit_softmax(features, labels, iterations=1200, learning_rate=0.12, l2=0.02):
    values = np.asarray(features, dtype=float)
    targets = np.asarray(labels, dtype=int)
    mean = values.mean(axis=0)
    scale = values.std(axis=0)
    scale[scale < 1e-8] = 1.0
    design = np.c_[np.ones(len(values)), (values - mean) / scale]
    weights = np.zeros((design.shape[1], 3))
    one_hot = np.eye(3)[targets]
    for _ in range(iterations):
        logits = design @ weights
        logits -= logits.max(axis=1, keepdims=True)
        probability = np.exp(logits)
        probability /= probability.sum(axis=1, keepdims=True)
        gradient = design.T @ (probability - one_hot) / len(design)
        gradient[1:] += l2 * weights[1:]
        weights -= learning_rate * gradient
    return SoftmaxModel(mean, scale, weights)


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


def _calibrated_temperature(model, features, labels):
    """Choose a single confidence temperature on chronological calibration data."""
    actual = np.asarray(labels, dtype=int)
    best_temperature = 1.0
    best_loss = float("inf")
    for temperature in np.linspace(0.6, 1.8, 49):
        candidate = SoftmaxModel(model.mean, model.scale, model.weights, float(temperature))
        probability = np.clip(candidate.predict_proba(features), 1e-9, 1)
        loss = float(-np.log(probability[np.arange(len(actual)), actual]).mean())
        if loss < best_loss:
            best_loss = loss
            best_temperature = float(temperature)
    return best_temperature


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


def train_time_split(feature_frame, train_fraction=0.8):
    if len(feature_frame) < 100:
        raise ValueError("At least 100 chronological matches are required")
    dates = np.sort(feature_frame.match_date.dt.normalize().unique())
    cutoff = pd.Timestamp(dates[max(1, int(len(dates) * train_fraction)) - 1])
    train = feature_frame[feature_frame.match_date <= cutoff]
    validation = feature_frame[feature_frame.match_date > cutoff]
    label_map = {"Home": 0, "Draw": 1, "Away": 2}
    train_dates = np.sort(train.match_date.dt.normalize().unique())
    calibration_cutoff = pd.Timestamp(train_dates[max(1, int(len(train_dates) * 0.8)) - 1])
    fit_rows = train[train.match_date <= calibration_cutoff]
    calibration_rows = train[train.match_date > calibration_cutoff]
    base_model = fit_softmax(fit_rows[list(FEATURES)], fit_rows.actual_result.map(label_map))
    temperature = _calibrated_temperature(
        base_model,
        calibration_rows[list(FEATURES)],
        calibration_rows.actual_result.map(label_map),
    ) if not calibration_rows.empty else 1.0
    refit = fit_softmax(train[list(FEATURES)], train.actual_result.map(label_map))
    model = SoftmaxModel(refit.mean, refit.scale, refit.weights, temperature)
    probabilities = model.predict_proba(validation[list(FEATURES)])
    baseline_prevalence = np.bincount(
        train.actual_result.map(label_map), minlength=3,
    ) / len(train)
    metrics = _metrics(
        probabilities, validation.actual_result.map(label_map), baseline_prevalence,
    )
    metrics.update({
        "temperature": temperature,
        "calibration_matches": int(len(calibration_rows)),
        "validation_matches": int(len(validation)),
    })
    metrics.update(_confidence_backtest(
        probabilities, validation.actual_result.map(label_map),
    ))
    league_backtest = []
    for league in sorted(validation.league.unique()):
        mask = validation.league.to_numpy() == league
        league_probabilities = probabilities[mask]
        league_actual = validation.loc[mask, "actual_result"].map(label_map).to_numpy()
        league_backtest.append({
            "league": league,
            "matches": int(mask.sum()),
            "accuracy": float((league_probabilities.argmax(axis=1) == league_actual).mean()),
            "log_loss": float(-np.log(np.clip(
                league_probabilities[np.arange(len(league_actual)), league_actual], 1e-9, 1,
            )).mean()),
        })
    metrics["league_backtest"] = league_backtest
    metrics["outcome_backtest"] = _outcome_backtest(
        probabilities, validation.actual_result.map(label_map),
    )
    uncalibrated = SoftmaxModel(refit.mean, refit.scale, refit.weights)
    raw_metrics = _metrics(
        uncalibrated.predict_proba(validation[list(FEATURES)]),
        validation.actual_result.map(label_map), baseline_prevalence,
    )
    metrics["uncalibrated_log_loss"] = raw_metrics["log_loss"]
    final_fit = fit_softmax(feature_frame[list(FEATURES)], feature_frame.actual_result.map(label_map))
    final_model = SoftmaxModel(final_fit.mean, final_fit.scale, final_fit.weights, temperature)
    return final_model, cutoff, train, validation, probabilities, metrics


def walk_forward_backtest(feature_frame):
    """Test each later season with a model trained only on earlier seasons."""
    label_map = {"Home": 0, "Draw": 1, "Away": 2}
    rows = []
    for season in sorted(feature_frame.season.unique()):
        earlier = feature_frame[feature_frame.season < season]
        test = feature_frame[feature_frame.season == season]
        if len(earlier) < 100 or len(test) < 30:
            continue
        model, _, _, _, _, _ = train_time_split(earlier)
        probabilities = model.predict_proba(test[list(FEATURES)])
        actual = test.actual_result.map(label_map).to_numpy()
        baseline = np.bincount(earlier.actual_result.map(label_map), minlength=3) / len(earlier)
        metrics = _metrics(probabilities, actual, baseline)
        rows.append({
            "season": int(season), "matches": len(test),
            "accuracy": metrics["accuracy"], "log_loss": metrics["log_loss"],
            "baseline_accuracy": metrics["baseline_accuracy"],
            "baseline_log_loss": metrics["baseline_log_loss"],
        })
    return rows


def _input_fingerprint(matches, upcoming):
    """Hash model inputs and implementation so unchanged refreshes skip training."""
    digest = hashlib.sha256(MODEL_VERSION.encode())
    for path in (Path(__file__), Path(__file__).with_name("prediction_features.py")):
        stat = path.stat()
        digest.update(f"{stat.st_size}:{stat.st_mtime_ns}".encode())
    for frame, columns in (
        (matches, ["league", "season", "match_date", "home_team", "away_team",
                   "home_goals", "away_goals", "home_sot", "away_sot"]),
        (upcoming, ["league", "season", "match_date", "home_team", "away_team"]),
    ):
        available = [column for column in columns if column in frame]
        ordered = frame[available].sort_values(available).reset_index(drop=True)
        digest.update(pd.util.hash_pandas_object(ordered, index=False).values.tobytes())
    return digest.hexdigest()


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


def sync_predictions(db=DB, force=False):
    with connect(db) as con:
        matches, upcoming = load_match_inputs(con)
        fingerprint = _input_fingerprint(matches, upcoming)
        cached = con.execute(
            "SELECT fingerprint FROM source_sync_cache WHERE source='prediction-model'"
        ).fetchone()
        model_record = con.execute(
            "SELECT model_id, metrics FROM prediction_models ORDER BY trained_at DESC LIMIT 1"
        ).fetchone()
        _reconcile_forecast_history(con, matches)
        if not force and cached and cached[0] == fingerprint and model_record:
            return {"model_id": model_record[0], "status": "cached", **json.loads(model_record[1])}
        feature_frame = build_match_features(matches)
        model, cutoff, train, validation, probabilities, metrics = train_time_split(feature_frame)
        metrics.update({
            "shot_coverage": float((matches.home_sot.notna() & matches.away_sot.notna()).mean()),
            "feature_count": len(FEATURES),
            "walk_forward": walk_forward_backtest(feature_frame),
        })
        model_id = f"{MODEL_VERSION}-{datetime.now():%Y%m%d%H%M%S%f}"
        validation_rows = validation[["league", "season", "match_date", "home_team", "away_team", "actual_result"]].copy()
        validation_rows["predicted_result"] = CLASS_NAMES[probabilities.argmax(axis=1)]
        validation_rows[["home_probability", "draw_probability", "away_probability"]] = probabilities
        validation_rows.insert(0, "prediction_kind", "validation")
        validation_rows.insert(0, "model_id", model_id)

        forecast_rows = pd.DataFrame()
        if not upcoming.empty:
            future = future_features(matches, upcoming)
            future_probabilities = model.predict_proba(future[list(FEATURES)])
            forecast_rows = future[["league", "season", "match_date", "home_team", "away_team"]].copy()
            forecast_rows["actual_result"] = None
            forecast_rows["predicted_result"] = CLASS_NAMES[future_probabilities.argmax(axis=1)]
            forecast_rows[["home_probability", "draw_probability", "away_probability"]] = future_probabilities
            forecast_rows.insert(0, "prediction_kind", "forecast")
            forecast_rows.insert(0, "model_id", model_id)

        model_row = pd.DataFrame([{
            "model_id": model_id, "model_name": "Calibrated softmax · Elo, form and shots on target",
            "trained_at": datetime.now(), "validation_cutoff": cutoff.date(),
            "train_matches": len(train), "validation_matches": len(validation),
            "feature_names": json.dumps(FEATURES), "parameters": model.to_json(),
            "metrics": json.dumps(metrics),
        }])
        predictions = pd.concat([validation_rows, forecast_rows], ignore_index=True)
        if not forecast_rows.empty:
            history_rows = forecast_rows.drop(columns=["prediction_kind", "actual_result"]).copy()
            history_rows["issued_at"] = datetime.now()
            history_rows["actual_result"] = None
            history_rows["resolved_at"] = None
            history_rows = history_rows[[
                "model_id", "league", "season", "match_date", "home_team", "away_team",
                "predicted_result", "home_probability", "draw_probability", "away_probability",
                "issued_at", "actual_result", "resolved_at",
            ]]
            con.register("incoming_forecast_history", history_rows)
        con.register("incoming_model", model_row)
        con.register("incoming_predictions", predictions)
        con.execute("BEGIN")
        try:
            if not forecast_rows.empty:
                con.execute("INSERT OR IGNORE INTO forecast_history SELECT * FROM incoming_forecast_history")
            con.execute("DELETE FROM match_predictions")
            con.execute("DELETE FROM prediction_models")
            con.execute("INSERT INTO prediction_models SELECT * FROM incoming_model")
            con.execute("INSERT INTO match_predictions SELECT * FROM incoming_predictions")
            con.execute("DELETE FROM source_sync_cache WHERE source='prediction-model'")
            con.execute(
                "INSERT INTO source_sync_cache VALUES ('prediction-model', ?, current_timestamp)",
                [fingerprint],
            )
            con.execute("COMMIT")
        except Exception:
            con.execute("ROLLBACK")
            raise
        finally:
            con.unregister("incoming_model")
            con.unregister("incoming_predictions")
            if not forecast_rows.empty:
                con.unregister("incoming_forecast_history")
    return {"model_id": model_id, **metrics, "forecasts": len(forecast_rows)}


def main():
    parser = argparse.ArgumentParser(description="Train and evaluate the football result model")
    parser.add_argument("--force", action="store_true", help="Retrain even if inputs are unchanged")
    args = parser.parse_args()
    print(json.dumps(sync_predictions(force=args.force), indent=2))


if __name__ == "__main__":
    main()
