"""Time-series cross-validated hyperparameter search for logistic regression and LightGBM.

    uv run football-train-models --tune

Only the window before the first walk-forward test season is used (training seasons < S-1 for
the earliest test season S), so the leaderboard's test seasons never influence the choice.
TimeSeriesSplit cuts that window by date: every fold trains on earlier matches and is scored
on the block that follows; the last 15% of each fold's training rows is its calibration slice
(early stopping, temperature). Each trial is an MLflow child run under one parent.
"""

from __future__ import annotations

import itertools
import json

import numpy as np
from sklearn.model_selection import TimeSeriesSplit

from .evaluate import metrics
from .models import LightGBM, Logit

GRIDS = {
    "logreg": (lambda **p: Logit("logreg", C=p["C"], half_life=p["half_life"]),
               {"C": [0.01, 0.02, 0.05, 0.1, 0.3], "half_life": [3, 4, 6, 0]}),
    "lightgbm": (lambda **p: LightGBM(half_life=p["half_life"], num_leaves=p["num_leaves"],
                                      min_child_samples=p["min_child_samples"]),
                 {"num_leaves": [7, 15, 31], "min_child_samples": [100, 200, 400], "half_life": [4, 6]}),
}


def cv_score(window, make_model, n_splits=4):
    """Mean RPS / log loss over time-ordered folds of `window` (sorted by match_date)."""
    scores = []
    for fit_idx, test_idx in TimeSeriesSplit(n_splits=n_splits).split(window):
        fit_rows = window.iloc[fit_idx]
        cut = int(len(fit_rows) * 0.85)
        model = make_model().fit(fit_rows.iloc[:cut], fit_rows.iloc[cut:])
        test = window.iloc[test_idx]
        scores.append(metrics(model.predict_proba(test), test.outcome.to_numpy()))
    return {k: float(np.mean([s[k] for s in scores])) for k in ("rps", "log_loss", "accuracy")}


def tune(frame, first_test_season, models=("logreg", "lightgbm"), n_splits=4):
    import mlflow

    window = frame[(frame.outcome >= 0) & (frame.season < first_test_season - 1)]
    window = window.sort_values("match_date", kind="stable").reset_index(drop=True)
    best = {}
    with mlflow.start_run(run_name=f"tune-before-{first_test_season - 1}"):
        mlflow.log_params({"window_rows": len(window), "n_splits": n_splits,
                           "window_last_season": int(window.season.max())})
        for name in models:
            make, grid = GRIDS[name]
            trials = []
            for values in itertools.product(*grid.values()):
                params = dict(zip(grid, values))
                with mlflow.start_run(run_name=f"{name} {params}", nested=True):
                    mlflow.log_params({"model": name, **params})
                    result = cv_score(window, lambda: make(**params), n_splits)
                    mlflow.log_metrics(result)
                trials.append({**params, **result})
                print(json.dumps({"model": name, **trials[-1]}), flush=True)
            best[name] = min(trials, key=lambda t: t["rps"])
            mlflow.log_dict({"trials": trials, "best": best[name]}, f"{name}_trials.json")
    return best
