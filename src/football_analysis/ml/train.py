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
import pandas as pd

from ..config import DB, ROOT, current_season
from .evaluate import calibration_bins, score, walk_forward
from .models import candidates

EXPERIMENT = "match-outcome"
from . import TARGETS
INDEPENDENT = {"elo_logit", "logreg", "lightgbm", "poisson_dixon_coles", "ensemble", "stacked"}


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


def _mlflow(tracking_uri=None):
    import mlflow

    os.environ.setdefault("MLFLOW_DISABLE_AGENT_HINT", "1")
    mlflow.set_tracking_uri(tracking_uri or os.environ.get("MLFLOW_TRACKING_URI", f"sqlite:///{ROOT / 'mlflow.db'}"))
    mlflow.set_experiment(EXPERIMENT)
    return mlflow


def _test_seasons(frame):
    completed = sorted(frame.loc[frame.outcome >= 0, "season"].unique())
    return [s for s in completed if s < current_season()][-4:]


def train(db=DB, test_seasons=None, tracking_uri=None):
    mlflow = _mlflow(tracking_uri)
    frame = load_features(db)
    current = current_season()
    test_seasons = test_seasons or _test_seasons(frame)
    results = leaderboard(frame, test_seasons)

    rows, sha, stamp = [], _git_sha(), datetime.now().replace(microsecond=0)
    with mlflow.start_run(run_name=f"leaderboard-{stamp:%Y%m%d-%H%M}"):
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
                seasons = [{"season": int(season), **score(part)} for season, part in predictions.groupby("season")]
                rows.append({"run_id": run.info.run_id, "model": name, **overall, "trained_at": stamp,
                             "independent": name in INDEPENDENT, "bins": json.dumps(bins),
                             "seasons": json.dumps(seasons), "params": json.dumps(model.params(), default=float)})
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
        mlflow.log_table(board.drop(columns=["bins", "seasons", "params"]), "leaderboard.json")
    _publish(db, frame, board, champion, pd.concat([pred for pred, _ in results.values()], ignore_index=True), current)
    print(board.drop(columns=["bins", "seasons", "params", "run_id"]).to_string(index=False))
    return board


def _publish(db, frame, board, champion, oos, current):
    """Refit the champion on everything before the current season, score fixtures and
    the current season, and hand the result to the app's prediction tables."""
    from ..ingest import connect
    from .features import FEATURES
    from .publish import publish_to_app

    model = _candidate(champion)
    played = frame[frame.outcome >= 0]
    last_completed = played.loc[played.season < current, "season"].max()
    train_rows = played[played.season < last_completed]
    model.fit(train_rows, played[played.season == last_completed])
    target = frame[(frame.season >= current) & (frame.tier == 1)]
    p = model.predict_proba(target)
    predictions = target[["league", "season", "match_date", "home_team", "away_team", "outcome"]].assign(
        model=champion, home_probability=p[:, 0], draw_probability=p[:, 1], away_probability=p[:, 2],
        is_fixture=target.outcome < 0, issued_at=datetime.now().replace(microsecond=0),
    )
    with connect(db) as con:
        con.execute("CREATE SCHEMA IF NOT EXISTS ml")
        for table, data in (("model_runs", board), ("current_predictions", predictions), ("backtest_predictions", oos)):
            con.register("incoming", data)
            con.execute(f"CREATE OR REPLACE TABLE ml.{table} AS SELECT * FROM incoming")
            con.unregister("incoming")
        actual = con.sql("SELECT league, season, match_date, home_team, away_team, home_goals, away_goals "
                         "FROM marts.fct_match WHERE season >= ?", params=[current - 1]).df()
        print(json.dumps(publish_to_app(con, champion, board, oos, predictions, actual,
                                        len(train_rows), len(FEATURES))), flush=True)


def forecast(db=DB, max_age_days=7):
    """Routine refresh: refit only the current champion and re-score fixtures (seconds).

    Reuses the stored leaderboard and backtest; runs the full 8-model comparison instead
    when none exists or it is older than `max_age_days`.
    """
    with duckdb.connect(str(db), read_only=True) as con:
        tables = {r[0] for r in con.execute(
            "SELECT table_name FROM information_schema.tables WHERE table_schema = 'ml'").fetchall()}
        if not {"model_runs", "backtest_predictions"} <= tables:
            return train(db=db)
        board = con.sql("SELECT * FROM ml.model_runs").df()
        oos = con.sql("SELECT * FROM ml.backtest_predictions").df()
    trained = pd.to_datetime(board.trained_at).max()
    if board.empty or datetime.now() - trained > pd.Timedelta(days=max_age_days):
        return train(db=db)
    champion = board[board.is_champion].iloc[0].model
    _publish(db, load_features(db), board, champion, oos, current_season())
    print(json.dumps({"mode": "champion refit", "champion": champion, "leaderboard_from": str(trained)}), flush=True)
    return board


def main():
    parser = argparse.ArgumentParser(description="Walk-forward model leaderboard with MLflow tracking")
    parser.add_argument("--test-seasons", nargs="+", type=int)
    parser.add_argument("--quick", action="store_true",
                        help="Refit only the champion if the leaderboard is under 7 days old")
    parser.add_argument("--tune", action="store_true",
                        help="Time-series CV search for logistic regression and LightGBM (before the test seasons)")
    args = parser.parse_args()
    if args.quick:
        forecast()
    elif args.tune:
        from .tune import tune

        _mlflow()
        frame = load_features()
        print(json.dumps(tune(frame, min(args.test_seasons or _test_seasons(frame))), indent=1))
    else:
        train(test_seasons=args.test_seasons)


if __name__ == "__main__":
    main()
