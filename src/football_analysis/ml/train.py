"""Train every candidate, compare them walk-forward, track in MLflow, publish predictions.

    uv run football-train-models            # leaderboard + champion + forecasts
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
from datetime import datetime

import duckdb
import numpy as np
import pandas as pd

from ..config import DB, ROOT, current_season
from .evaluate import calibration_bins, score, walk_forward
from .models import candidates

EXPERIMENT = "match-outcome"
TARGETS = {"log_loss": 0.975, "rps": 0.200, "accuracy": 0.535, "ece": 0.02}
INDEPENDENT = {"elo_logit", "logreg", "lightgbm", "poisson_dixon_coles", "ensemble"}


def load_features(db=DB):
    with duckdb.connect(str(db), read_only=True) as con:
        frame = con.sql("SELECT * FROM ml.ml_match_features").df()
    return frame.sort_values("match_date", kind="stable").reset_index(drop=True)


def _git_sha():
    try:
        return subprocess.check_output(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, text=True).strip()
    except Exception:
        return "unknown"


def _candidate(name):
    return next(c for c in candidates() if c.name == name)


def leaderboard(frame, test_seasons):
    """Walk-forward predictions for every candidate on one common evaluation set."""
    common = (frame.tier == 1) & frame[["close_p_home", "close_p_draw", "close_p_away"]].notna().all(axis=1)
    results = {}
    for name in [c.name for c in candidates()]:
        predictions, last_model = walk_forward(frame, lambda n=name: _candidate(n), test_seasons, eval_mask=common)
        results[name] = (predictions, last_model)
        print(json.dumps({"model": name, **score(predictions)}), flush=True)
    return results


def train(db=DB, test_seasons=None, tracking_uri=None):
    import mlflow

    os.environ.setdefault("MLFLOW_DISABLE_AGENT_HINT", "1")
    mlflow.set_tracking_uri(tracking_uri or f"sqlite:///{ROOT / 'mlflow.db'}")
    mlflow.set_experiment(EXPERIMENT)
    frame = load_features(db)
    completed = sorted(frame.loc[frame.outcome >= 0, "season"].unique())
    current = current_season()
    test_seasons = test_seasons or [s for s in completed if s < current][-4:]
    results = leaderboard(frame, test_seasons)

    rows, sha, stamp = [], _git_sha(), datetime.now().replace(microsecond=0)
    with mlflow.start_run(run_name=f"leaderboard-{stamp:%Y%m%d-%H%M}") as parent:
        mlflow.set_tags({"git_sha": sha, "test_seasons": ",".join(map(str, test_seasons))})
        for name, (predictions, model) in results.items():
            overall = score(predictions)
            with mlflow.start_run(run_name=name, nested=True) as run:
                mlflow.log_params({"model": name, **model.params()})
                mlflow.log_metrics({k: v for k, v in overall.items() if k != "n"})
                for season, part in predictions.groupby("season"):
                    mlflow.log_metrics({f"{k}_{season}": v for k, v in score(part).items() if k != "n"})
                p = predictions[["p_home", "p_draw", "p_away"]].to_numpy()
                bins = calibration_bins(p, predictions.outcome.to_numpy())
                mlflow.log_dict({"bins": bins}, "calibration_bins.json")
                rows.append({"run_id": run.info.run_id, "model": name, **overall, "trained_at": stamp,
                             "independent": name in INDEPENDENT, "bins": json.dumps(bins)})
        board = pd.DataFrame(rows).sort_values("rps")
        champion = board[board.independent].iloc[0].model
        board["is_champion"] = board.model == champion
        market = board[board.model == "market_closing"].iloc[0]
        gaps = {f"target_{k}_met": bool(board.loc[board.model == champion, k].iloc[0] <= v) if k != "accuracy"
                else bool(board.loc[board.model == champion, k].iloc[0] >= v) for k, v in TARGETS.items()}
        mlflow.log_params({"champion": champion})
        mlflow.log_metrics({"champion_gap_to_market_log_loss":
                            float(board.loc[board.model == champion, "log_loss"].iloc[0] - market.log_loss),
                            **{k: float(v) for k, v in gaps.items()}})
        mlflow.log_table(board.drop(columns="bins"), "leaderboard.json")
    _publish(db, frame, board, champion, results, current)
    print(board.drop(columns=["bins", "run_id"]).to_string(index=False))
    return board


def _publish(db, frame, board, champion, results, current):
    """Refit the champion on everything before the current season and score fixtures/current season."""
    model = _candidate(champion)
    played = frame[frame.outcome >= 0]
    last_completed = played.loc[played.season < current, "season"].max()
    model.fit(played[played.season < last_completed], played[played.season == last_completed])
    target = frame[(frame.season >= current) & (frame.tier == 1)]
    p = model.predict_proba(target)
    predictions = target[["league", "season", "match_date", "home_team", "away_team", "outcome"]].assign(
        model=champion, home_probability=p[:, 0], draw_probability=p[:, 1], away_probability=p[:, 2],
        predicted_result=np.array(["Home", "Draw", "Away"])[p.argmax(1)],
        is_fixture=target.outcome < 0, issued_at=datetime.now().replace(microsecond=0),
    )
    oos = pd.concat([pred for pred, _ in results.values()], ignore_index=True)
    with duckdb.connect(str(db)) as con:
        con.execute("CREATE SCHEMA IF NOT EXISTS ml")
        for table, data in (("model_runs", board), ("current_predictions", predictions), ("backtest_predictions", oos)):
            con.register("incoming", data)
            con.execute(f"CREATE OR REPLACE TABLE ml.{table} AS SELECT * FROM incoming")
            con.unregister("incoming")


def main():
    parser = argparse.ArgumentParser(description="Walk-forward model leaderboard with MLflow tracking")
    parser.add_argument("--test-seasons", nargs="+", type=int)
    args = parser.parse_args()
    train(test_seasons=args.test_seasons)


if __name__ == "__main__":
    main()
