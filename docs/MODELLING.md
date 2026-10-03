# Match-outcome modelling

Goal: home/draw/away probabilities that are honest (calibrated) and as sharp as possible without
looking at betting odds, judged against the strongest public forecast, the bookmaker closing line.

## Data

`ml.ml_match_features`: 113k matches from 15 leagues (top flights plus the five second divisions),
2005/06 onwards. Second divisions matter: promoted clubs arrive with real form and ratings instead of a guess.

## Features (`football_analysis/ml/features.py`)

All computed from state strictly before the match date. State updates only after a whole match day,
so same-day results never leak into each other (tested in `tests/test_ml.py` and by a dbt test).

- **Elo** with a goal-margin multiplier and between-season regression. Clubs entering a league start
  at the mean of the destination's previous-season bottom three (promoted) or top three (relegated).
- **pi-ratings** (Constantinou & Fenton 2013): separate home and away strength.
- **Exponentially weighted form** (half-life 6 matches): points, goals for/against, shots on target
  for/against, shots, corners, plus venue-specific points and goal difference.
- Rest days, matches played this season, promoted flag, season progress.
- League base rates over the last 400 matches (home-win, draw and goal rates), which absorb eras such
  as behind-closed-doors football.
- Market features (opening-odds probabilities with the margin removed) are used **only** by the clearly
  labelled `market_blend` model.

## Candidates (`football_analysis/ml/models.py`)

Base-rate guess · Elo-only logistic · multinomial logistic regression · LightGBM (early stopping) ·
Poisson goals with a Dixon-Coles low-score correction (also gives scorelines and over/under) ·
ensemble (convex blend with weights fitted on the calibration season) · stacked (multinomial logistic
meta-learner on member log-probabilities, fitted on out-of-fold predictions from the last six seasons of the
training window only); logistic regression and LightGBM use recency-weighted training · model + opening odds ·
bookmaker closing line (benchmark only). Each model gets temperature calibration on the calibration season.

## Evaluation (`football_analysis/ml/evaluate.py`)

Walk-forward by season: to predict season S, train on seasons < S−1 and calibrate on S−1. Scored on the
last four completed seasons, top flights only, matches with closing odds, so every model is compared on the
same 13,061 matches. Metrics: ranked probability score (primary), log loss, Brier score, accuracy and
expected calibration error. The champion is the independent model (no odds) with the lowest RPS.

Acceptance targets (`football_analysis.ml.TARGETS`): log loss ≤ 0.975 ✅ 0.9670 · RPS ≤ 0.200 ✅ 0.1946 ·
ECE ≤ 0.02 ✅ 0.0048 · accuracy ≥ 53.5% ✗ 53.4% (standard error ≈ ±0.44 points, so not distinguishable).

Tuning record: recency-weighted training (weight halves every 4 seasons for logistic regression, 6 for
LightGBM) gave the only consistent gain. Elo K (15/20/28), form half-life (4/6/10) and between-season
regression (0.65/0.8) all landed within ±0.0001 RPS of each other, i.e. the features are at a plateau.

Honest reading: accuracy is a poor target for three-way outcomes (draws are rarely the most likely result).
The champion closes 89% of the gap between a base-rate guess and the closing line. The remaining ~0.013 log
loss to the market is typical of public-data models; the market prices team news, injuries and line-ups
that results-only features cannot see.

Stacking and time-series tuning (October 2026). Same 13,061 matches; Δ is RPS minus the ensemble's, with the
paired standard error over matches (negative would be better):

| Variant | RPS | Log loss | Accuracy | Δ RPS ± SE |
|---|---|---|---|---|
| Ensemble (champion) | 0.19458 | 0.9670 | 53.4% | — |
| Stacked, 6 out-of-fold seasons | 0.19475 | 0.9680 | 53.6% | +0.00017 ± 0.00010 |
| Ensemble with tuned members | 0.19467 | 0.9672 | 53.4% | +0.00009 ± 0.00004 |
| Logistic regression, tuned (C 0.02, half-life 6) | 0.19478 | 0.9679 | 53.2% | +0.00020 ± 0.00008 |
| LightGBM, tuned (7 leaves, min child 100) | 0.19493 | 0.9685 | 53.4% | +0.00035 ± 0.00011 |

Nothing beat the ensemble. The stack loses by 1.6 standard errors (not distinguishable; 3- and 4-fold stacks were
worse, 0.19517 and 0.19492, so more out-of-fold seasons help, and the fold count was picked after seeing these
scores). `football-train-models --tune` (TimeSeriesSplit, four date-ordered folds before the first test season, one
MLflow child run per trial) moved CV RPS by under 0.00006, and its winners did slightly *worse* walk-forward, so the
defaults stay. The stack remains a leaderboard candidate; the champion rule is unchanged.

## Tracking and serving

Two modes. `football-train-models` runs the full walk-forward leaderboard (~3 min). Routine refreshes
(`football-sync`, the Settings button, Dagster) call `ml.train.forecast()`, which refits only the stored
champion and re-scores fixtures in ~15 s, and falls back to the full leaderboard when the stored one is
missing or more than 7 days old. Provisional OpenFootball scores (`fct_match.is_provisional`) count as
results, so form and Elo move as soon as a score is known.


`football-train-models` logs one parent MLflow run per leaderboard with a nested run per model: params,
overall and per-season metrics, calibration bins, the git SHA and the leaderboard table. It then refits the
champion on all seasons before the current one, writes `ml.model_runs` / `ml.current_predictions` /
`ml.backtest_predictions`, and fills the app's `prediction_models`, `match_predictions` and `forecast_history`
tables so `/api/v1/predictions` keeps its contract. `/api/v1/models` serves the leaderboard to the Model Lab.

## Next levers

Model choice and hyperparameters are at a plateau. Remaining gains need new information: expected-goals proxies
when a free shot-location source exists, and line-up/injury signals (the main thing the closing line prices in).
