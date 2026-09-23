"""Leakage-aware football result probabilities using a compact softmax model."""

from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

from .config import DB
from .ingest import connect
from .prediction_features import FEATURES, build_match_features, future_features, load_match_inputs

MODEL_VERSION = "softmax-form-shots-v3"
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
    uncalibrated = SoftmaxModel(refit.mean, refit.scale, refit.weights)
    raw_metrics = _metrics(
        uncalibrated.predict_proba(validation[list(FEATURES)]),
        validation.actual_result.map(label_map), baseline_prevalence,
    )
    metrics["uncalibrated_log_loss"] = raw_metrics["log_loss"]
    final_fit = fit_softmax(feature_frame[list(FEATURES)], feature_frame.actual_result.map(label_map))
    final_model = SoftmaxModel(final_fit.mean, final_fit.scale, final_fit.weights, temperature)
    return final_model, cutoff, train, validation, probabilities, metrics


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
        if not force and cached and cached[0] == fingerprint and model_record:
            return {"model_id": model_record[0], "status": "cached", **json.loads(model_record[1])}
        feature_frame = build_match_features(matches)
        model, cutoff, train, validation, probabilities, metrics = train_time_split(feature_frame)
        metrics.update({
            "shot_coverage": float((matches.home_sot.notna() & matches.away_sot.notna()).mean()),
            "feature_count": len(FEATURES),
        })
        model_id = f"{MODEL_VERSION}-{datetime.now():%Y%m%d%H%M%S}"
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
        con.register("incoming_model", model_row)
        con.register("incoming_predictions", predictions)
        con.execute("BEGIN")
        try:
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
    return {"model_id": model_id, **metrics, "forecasts": len(forecast_rows)}


def main():
    parser = argparse.ArgumentParser(description="Train and evaluate the football result model")
    parser.add_argument("--force", action="store_true", help="Retrain even if inputs are unchanged")
    args = parser.parse_args()
    print(json.dumps(sync_predictions(force=args.force), indent=2))


if __name__ == "__main__":
    main()
