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
meta-learner on out-of-fold member log-probabilities from six earlier seasons); logistic regression and
LightGBM use recency-weighted training · model + opening odds · bookmaker closing line (benchmark only).
Elo-only, logistic regression, LightGBM, Poisson, the stack and the odds blend get temperature calibration on
the calibration season; the ensemble blends already-calibrated members, and the base rate and closing line
are used as is.

## Evaluation (`football_analysis/ml/evaluate.py`)

Walk-forward by season: to predict season S, train on seasons < S−1 and calibrate on S−1. Scored on the
last four completed seasons, top flights only, matches with closing odds, so every model is compared on the
same 13,061 matches. Metrics: ranked probability score (primary), log loss, Brier score, accuracy and
expected calibration error. The champion is the independent model (no odds) with the lowest RPS.

Acceptance targets (`football_analysis.ml.TARGETS`): log loss ≤ 0.975 ✅ 0.9617 · RPS ≤ 0.200 ✅ 0.1928 ·
ECE ≤ 0.02 ✅ 0.0026 · accuracy ≥ 53.5% ✅ 54.0%. The stack edges the blend by 0.00002 RPS, well inside noise.

**Market-implied strength** (`market_strength_diff`): an Elo-style rating per club that moves towards each
*past* match's margin-free opening log-odds (home vs away, plus a learned league home advantage), updated
after the match day like every other state. A forecast never sees its own match's prices, so the no-odds
contract holds; entering clubs start at the league's edge, as for Elo. It lowered logistic-regression RPS
from 0.1947 to 0.1929 on the test seasons. Its step size (0.25) was picked on 2018–2021, not the test seasons.

Tried and dropped (no gain on 2018–2021): a finishing residual (goals − 0.3 × shots on target, half-life 20)
and seasons in the top flight over the last five. Regressing a promoted/relegated club's entry Elo like every
staying club improved Elo-only (0.2031 → 0.2027 RPS on 2018–2021) and is neutral for the full models.

Tuning record: recency-weighted training (weight halves every 4 seasons for logistic regression, 6 for
LightGBM) gave the only consistent gain. Elo K (15/20/28), form half-life (4/6/10) and between-season
regression (0.65/0.8) all landed within ±0.0001 RPS of each other, i.e. the features are at a plateau.

Honest reading: accuracy is a poor target for three-way outcomes (draws are rarely the most likely result).
The champion closes 94% of the gap between a base-rate guess and the closing line. The remaining ~0.008 log
loss to the market is the part it prices from team news, injuries and line-ups at kick-off.

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

`ml/tune.py` already runs time-series cross-validation for logistic regression and LightGBM; its best
parameters are not yet fed back into `candidates()`. Remaining feature levers: lineup continuity from
`fct_match_lineup` and fixture congestion including cups, both limited today by source coverage.
