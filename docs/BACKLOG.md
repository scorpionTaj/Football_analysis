# Backlog

Open work only. Finished iterations (FA-001 … FA-092, the Next.js cutover and the 2026-10 data
engineering / data science restructure) are recorded in git history.

## Data engineering
- [ ] Move the API's remaining queries from `main` app tables onto dbt marts, then rename the extractor tables into a `raw` schema.
- [ ] Remove the per-partition PostgreSQL match read model (`api/postgres_matches.py`, `football-publish-matches`, `FOOTBALL_MATCH_READ_BACKEND`); `football-publish` now serves every table.
- [ ] Run Dagster schedules as a long-lived service (daemon) on the host that owns the DuckDB file.
- [ ] Add dbt tests for tournament and player marts once those tables are modelled in dbt.
- [ ] Seek a permitted full-season fixture source for Belgium, Turkey and Greece (see `FUTURE_FIXTURE_SOURCES.md`).

## Data science
- [ ] Tune the ensemble with time-series cross-validation, logging each trial as an MLflow child run.
- [ ] Add expected-goals or shot-quality inputs when a free shot-location source exists.
- [ ] Stack models (out-of-fold meta-learner) instead of a fixed convex blend, and compare on walk-forward RPS.
- [ ] Optional API-Football current-squad adapter once a free key is configured (see `PLAYER_DB_RESEARCH.md`).

## Frontend
- [ ] Split the remaining Overview charts into their own components (the transfer market is already separate).
- [ ] Extend the axe accessibility scans to Model Lab and Data Quality (needs mocks for `/models` and `/pipeline`).
- [ ] Lighthouse budget (performance and accessibility ≥ 90) on Overview and Predictions in CI.
