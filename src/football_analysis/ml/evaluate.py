"""Proper scoring rules and season-by-season walk-forward evaluation."""

from __future__ import annotations

import numpy as np
import pandas as pd

from .models import EPS, usable


def rps(p, y):
    """Ranked probability score for ordered outcomes H < D < A (lower is better)."""
    onehot = np.eye(3)[y]
    return float(np.mean(np.sum((np.cumsum(p, 1)[:, :2] - np.cumsum(onehot, 1)[:, :2]) ** 2, axis=1) / 2))


def ece(p, y, bins=10):
    """Expected calibration error over all three outcome probabilities."""
    probs, hits = p.ravel(), np.eye(3)[y].ravel()
    edges = np.minimum((probs * bins).astype(int), bins - 1)
    return float(sum(abs(probs[edges == b].mean() - hits[edges == b].mean()) * (edges == b).mean()
                     for b in range(bins) if (edges == b).any()))


def metrics(p, y):
    p = np.clip(p, EPS, 1)
    return {
        "log_loss": float(-np.mean(np.log(p[np.arange(len(y)), y]))),
        "rps": rps(p, y),
        "brier": float(np.mean(np.sum((p - np.eye(3)[y]) ** 2, axis=1))),
        "accuracy": float(np.mean(p.argmax(1) == y)),
        "ece": ece(p, y),
        "n": int(len(y)),
    }


def calibration_bins(p, y, bins=10):
    rows = []
    for outcome, label in enumerate(("Home", "Draw", "Away")):
        probs, hits = p[:, outcome], (y == outcome)
        edges = np.minimum((probs * bins).astype(int), bins - 1)
        for b in range(bins):
            mask = edges == b
            if mask.sum() >= 20:
                rows.append({"outcome": label, "bin": b, "predicted": float(probs[mask].mean()),
                             "observed": float(hits[mask].mean()), "n": int(mask.sum())})
    return rows


def walk_forward(frame: pd.DataFrame, make_model, test_seasons, eval_mask=None):
    """For each test season S: train on seasons < S-1, calibrate on S-1, test on S.

    `eval_mask` restricts scoring (e.g. top-flight leagues) while training still
    uses every league. Returns stacked out-of-sample predictions.
    """
    played = frame[frame.outcome >= 0]
    out = []
    for season in test_seasons:
        train = played[played.season < season - 1]
        calib = played[played.season == season - 1]
        test = played[played.season == season]
        if eval_mask is not None:
            test = test[eval_mask.loc[test.index]]
        model = make_model()
        train, calib_used = train[usable(train, model)], calib[usable(calib, model)]
        test = test[usable(test, model)]
        if test.empty or train.empty:
            continue
        model.fit(train, calib_used)
        p = model.predict_proba(test)
        out.append(test[["league", "season", "match_date", "home_team", "away_team", "outcome"]].assign(
            p_home=p[:, 0], p_draw=p[:, 1], p_away=p[:, 2], model=model.name))
    return pd.concat(out, ignore_index=True) if out else pd.DataFrame(), model


def score(predictions: pd.DataFrame):
    p = predictions[["p_home", "p_draw", "p_away"]].to_numpy()
    return metrics(p, predictions.outcome.to_numpy())
