# Data model

The warehouse lives in one DuckDB file (`data/football.duckdb`) and is built by the dbt project in
`warehouse/`. Every model and test runs with `dbt build`; Dagster runs the same build as the
`warehouse` asset group, and CI runs it on fixture data (`scripts/ci_warehouse.sh`).

## Layers

| Layer | Schema | Materialization | Purpose |
|---|---|---|---|
| Landing | files in `data/raw/<yyYY>/<league>.csv` | dbt external source `landing.football_data_csv` | Football-Data CSVs as published (UTF-8 normalized only) |
| Raw app tables | `main` | written by Python extractors | current results, events, tournaments, players, media, legacy caches |
| Staging | `staging` | views | typing, renaming, quarantine rules |
| Intermediate | `intermediate` | tables | reshapes reused by several marts |
| Marts | `marts` | tables | what the API and analysis read |
| ML | `ml` | tables | features, leaderboard, predictions |
| Reference | `reference` | seeds | `leagues` (code, name, country, tier) |

## Models and grain

| Model | Grain | Notes |
|---|---|---|
| `stg_fd__results` | one row per CSV match row | guarantees optional columns across eras (`BbAv*` → `Avg*`), nulls impossible shots-on-target pairs |
| `stg_app__fixtures` | one row per provider fixture row | provider names reconciled later with `teams.team_key` |
| `fct_match` | match (`match_id` = md5 of league, season, date, home, away) | 113k matches, 15 leagues, 2005+; opening/closing odds with margin-free closing probabilities; impossible price sets quarantined |
| `int_team_matches` | team × match | two rows per match, points and venue |
| `mart_team_season` | league × season × team | reconstructed table with position |
| `ml_match_features` | match or upcoming fixture | 34 leakage-safe features + market features + targets (`outcome` −1 for fixtures); Python model calling `football_analysis.ml.features.build_features` |

## Data tests (all must pass)

- Generic: unique/not-null keys, `relationships` (`fct_match.league` → `leagues`), accepted values for result, venue and outcome, unique league-season-team and match-feature grains.
- `assert_sot_le_shots`: shots on target never exceed shots.
- `assert_no_future_results`, `assert_match_dates_within_season`.
- `assert_close_odds_overround_sane`: bookmaker margin between 0.98 and 1.25.
- `assert_complete_double_round_robin`: every completed top-five season has n·(n−1) matches. Known exception: Ligue 1 2019/20 (abandoned, COVID-19).
- `assert_one_match_per_team_per_day`: guards the same-day snapshot assumption that keeps features leakage-free.
- Source freshness on `recent_matches` and `recent_events` (`dbt source freshness`).

Data issues these tests surfaced and the fixes: one Latin-1 file (Serie B 2018/19, re-encoded on landing), two broken closing-price rows (quarantined), fixtures duplicated across providers under different club spellings (reconciled by canonical key), and odds columns missing in some eras (guarded in staging).

## Serving

`football-publish` copies the `main` app tables plus `mart_team_season` and `model_runs` to the private PostgreSQL schema, swapping only tables whose row digest changed. Large analytical tables stay in DuckDB because the Supabase free tier caps the database at 500 MB.
