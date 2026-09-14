"""Leakage-aware football result probabilities using a compact softmax model."""

from __future__ import annotations

import argparse
import json
from collections import defaultdict, deque
from dataclasses import dataclass
from datetime import datetime

import numpy as np
import pandas as pd

from .config import DB, current_season
from .ingest import connect
from .teams import team_key

FEATURES = (
    "elo_gap", "home_form_ppg", "away_form_ppg", "home_goals_for",
    "away_goals_for", "home_goals_against", "away_goals_against",
    "home_rest_days", "away_rest_days",
)
FORM_WINDOW = 10
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


def _form(history, key, window):
    rows = list(history[key])[-window:]
    if not rows:
        return 1.0, 1.2, 1.2
    return (
        sum(row[0] for row in rows) / len(rows),
        sum(row[1] for row in rows) / len(rows),
        sum(row[2] for row in rows) / len(rows),
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
                history.clear()
            previous_season = season
            for match_date, day_matches in season_matches.groupby("match_date", sort=True):
                date = pd.Timestamp(match_date)
                day_rows = []
                changes = defaultdict(float)
                for match in day_matches.itertuples(index=False):
                    home_key, away_key = team_key(match.home_team), team_key(match.away_team)
                    home_ppg, home_gf, home_ga = _form(history, home_key, form_window)
                    away_ppg, away_gf, away_ga = _form(history, away_key, form_window)
                    home_elo, away_elo = ratings[home_key], ratings[away_key]
                    features = [
                        (home_elo + 60 - away_elo) / 400,
                        home_ppg / 3, away_ppg / 3, home_gf, away_gf, home_ga, away_ga,
                        _rest(last_played, home_key, date), _rest(last_played, away_key, date),
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
                    day_rows.append((home_key, away_key, home_points, away_points, match.home_goals, match.away_goals))
                for key, change in changes.items():
                    ratings[key] += change
                for home_key, away_key, hp, ap, hg, ag in day_rows:
                    history[home_key].append((hp, hg, ag))
                    history[away_key].append((ap, ag, hg))
                    last_played[home_key] = date
                    last_played[away_key] = date
    return pd.DataFrame(records)


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


def _metrics(probabilities, labels):
    actual = np.asarray(labels, dtype=int)
    clipped = np.clip(probabilities, 1e-9, 1)
    predicted = probabilities.argmax(axis=1)
    prevalence = np.bincount(actual, minlength=3) / len(actual)
    baseline = np.tile(prevalence, (len(actual), 1))
    return {
        "accuracy": float((predicted == actual).mean()),
        "log_loss": float(-np.log(clipped[np.arange(len(actual)), actual]).mean()),
        "brier_score": float(np.square(probabilities - np.eye(3)[actual]).sum(axis=1).mean()),
        "baseline_accuracy": float(prevalence.max()),
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
    metrics = _metrics(probabilities, validation.actual_result.map(label_map))
    metrics.update({
        "temperature": temperature,
        "calibration_matches": int(len(calibration_rows)),
        "validation_matches": int(len(validation)),
    })
    uncalibrated = SoftmaxModel(refit.mean, refit.scale, refit.weights)
    raw_metrics = _metrics(
        uncalibrated.predict_proba(validation[list(FEATURES)]),
        validation.actual_result.map(label_map),
    )
    metrics["uncalibrated_log_loss"] = raw_metrics["log_loss"]
    final_fit = fit_softmax(feature_frame[list(FEATURES)], feature_frame.actual_result.map(label_map))
    final_model = SoftmaxModel(final_fit.mean, final_fit.scale, final_fit.weights, temperature)
    return final_model, cutoff, train, validation, probabilities, metrics


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
    # Build each future row immediately after history by using a harmless draw, then
    # retain only its pre-match features. Source fixtures are after known results.
    features = build_match_features(combined, form_window=form_window)
    keys = sentinel[["league", "season", "match_date", "home_team", "away_team"]].copy()
    keys["match_date"] = pd.to_datetime(keys.match_date)
    return keys.merge(
        features[features.actual_result.isna()].drop(columns="actual_result"),
        on=["league", "season", "match_date", "home_team", "away_team"], how="left",
    )


def sync_predictions(db=DB):
    with connect(db) as con:
        matches = con.sql("SELECT * FROM matches").df()
        recent = con.sql("SELECT * FROM recent_matches").df()
        if not recent.empty:
            matches = pd.concat([matches, recent], ignore_index=True).drop_duplicates(
                ["league", "season", "home_team", "away_team"], keep="last",
            )
        feature_frame = build_match_features(matches)
        model, cutoff, train, validation, probabilities, metrics = train_time_split(feature_frame)
        model_id = f"softmax-form-elo-v2-{datetime.now():%Y%m%d%H%M%S}"
        validation_rows = validation[["league", "season", "match_date", "home_team", "away_team", "actual_result"]].copy()
        validation_rows["predicted_result"] = CLASS_NAMES[probabilities.argmax(axis=1)]
        validation_rows[["home_probability", "draw_probability", "away_probability"]] = probabilities
        validation_rows.insert(0, "prediction_kind", "validation")
        validation_rows.insert(0, "model_id", model_id)

        upcoming = con.sql("""
            SELECT league, season, match_date, home_team, away_team
            FROM recent_events WHERE event_kind='next'
        """).df()
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
            "model_id": model_id, "model_name": "Calibrated softmax · Elo + 10-match form",
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
    parser.parse_args()
    print(json.dumps(sync_predictions(), indent=2))


if __name__ == "__main__":
    main()
