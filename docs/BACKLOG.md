# Backlog

Open work only. Finished iterations (FA-001 … FA-092, the Next.js cutover and the 2026-10 data
engineering / data science restructure) are recorded in git history.

## Data engineering
- [ ] Model tournaments, players and match context in dbt, then move the API's queries from `main` app tables onto those marts. (Domestic results are already tested in dbt; repointing the API now would change what pages show, because the marts cover 2005+ and second divisions while the dashboard shows the validated five-season window.)
- [ ] Optional: run the Dagster daemon instead of the systemd timers when its UI/lineage is wanted in production.
- [ ] Add dbt tests for tournament and player marts once those tables are modelled in dbt.
- [ ] Seek a permitted full-season fixture source for Belgium, Turkey and Greece.

## Data science
- [ ] Tune the ensemble with time-series cross-validation, logging each trial as an MLflow child run.
- [ ] Add expected-goals or shot-quality inputs when a free shot-location source exists.
- [ ] Stack models (out-of-fold meta-learner) instead of a fixed convex blend, and compare on walk-forward RPS.
- [ ] Optional API-Football current-squad adapter once a free key is configured.

## Frontend
- [ ] Lighthouse budget (performance and accessibility ≥ 90) on Overview and Predictions in CI.
