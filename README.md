# football_analysis

Linux-friendly football analytics with FastAPI, DuckDB and a responsive Next.js/HeroUI frontend. No payment, API key, or subscription is required.

## Start with the existing database

```bash
cd /home/scorpiontaj/Projects/Football_analysis
uv sync --extra dev
uv run football-api
```

In a second terminal:

```bash
cd /home/scorpiontaj/Projects/Football_analysis/frontend
npm install
npm run dev -- --port 3001
```

For a new database, stop `football-api` first and run one historical bootstrap command:

```bash
cd /home/scorpiontaj/Projects/Football_analysis
uv run football-sync --bootstrap
```

For later updates, use `uv run football-sync`. This incremental command refreshes the current season, match details and predictions; unchanged source partitions and model inputs are skipped. `--step 1` through `--step 4` chooses a shallower refresh, `--competitions E0 SP1` narrows its scope, and `--force` bypasses freshness checks. Run the command while the API is stopped because DuckDB has one writer; while the API is running, use the equivalent four-step refresh in Settings instead. Refresh progress persists across application restarts. Stages commit independently: after a failure, completed stages remain applied and the failed stage may have partial source updates; rerunning the incremental command resumes safely.

Alternatively: create a Python 3.11+ virtual environment and run `pip install -e '.[dev]'`.

Open http://localhost:3001 while FastAPI runs at http://127.0.0.1:8000. Network is needed for a source refresh; current CSVs and standings are checked at most every six hours, recent event lists hourly, completed event details daily, and featured player profiles weekly. Historical partitions, unavailable artwork and unchanged model inputs are reused. Settings includes the same four-step refresh depth control; API reads pause while DuckDB refreshes and resume against the updated snapshot. The navbar refresh button only invalidates frontend queries. Use `uv run football-ingest --offline data/raw` for offline replay; `--refresh` redownloads archives. `--seasons 2024 --leagues E0` is useful for a small trial. Existing valid partitions remain intact if a source fails.

The normal sync fills featured clubs and competition badges, then reuses them on later runs. An exhaustive backfill is optional: `uv run football-sync --all-media --max-teams 100` checks a bounded batch of missing teams; repeat it to continue. Each ten-team batch is saved immediately, and provider "not found" responses are cached for 30 days. The free image API is paced, so an exhaustive one-shot run can take many minutes. The open player importer skips its large CSV rebuild when the local snapshot and importer are unchanged. `football-api` is a server and intentionally stays running until stopped.

## Scope

All clubs currently present across the Premier League, La Liga, Bundesliga, Serie A, Ligue 1, Eredivisie, Primeira Liga, Belgian Pro League, Turkish Süper Lig and Greek Super League are selectable. The grouped tournament workflow also covers UEFA club competitions, major English/Spanish/German/Italian/Dutch cups and super cups, the Euros, Copa América, AFCON, Asian Cup, FIFA Club World Cup and FIFA World Cup whenever the configured sources publish an edition.

The analytical range is 2021/22–2025/26 plus the live 2026/27 campaign. The July rollover selects five candidate completed seasons; each completed CSV must independently pass full double-round-robin coverage checks. Live rows are clearly labelled as partial and never presented as a completed season.

Dashboard: one typo-tolerant platform search, three domestic analysis modes and nine focused pages: Overview, Tournaments, Analysis lab, League tables, Club lab, Shot lab, Match Centre, Players and Data quality. Match Centre search runs across the filtered data before pagination, and its detail URLs survive reloads. Every listed match opens a factual story with stored statistics, real manager/formation context when published, named goals/cards/substitutions/missed penalties and verified lineup positions and portraits on a responsive pitch. Club head-to-head reads the unified league-and-cup store. The Analysis lab slices domestic and tournament data by competition, edition, team and venue; ranks teams by seven metrics; builds a correlation matrix; analyzes first-half scoring, corners, fouls, cards and referee trends; and exports both the rankings and exact match slice.

The predictive section trains a regularized three-outcome softmax model on leakage-safe pre-match Elo, ten-match rolling points, scoring, conceding, shots on target and rest-day features. Confidence temperature is learned from an earlier chronological calibration window; the latest 20% of match dates remain outside fitting and calibration. On the current 2,023-match holdout it reaches 51.4% accuracy versus a 43.2% training-prevalence baseline and improves log loss from 1.075 to 0.997. At a 75% predicted-probability threshold, 65 holdout matches qualified and 81.5% were called correctly—but that is only 3.2% of matches, with a wide 70.4–89.1% confidence interval. The Predictions page shows coverage, per-league and per-outcome diagnostics, season-by-season walk-forward results, and a forecast journal that preserves issued probabilities while later filling in actual results. Available future fixtures are cached as home/draw/away probabilities, while conservative current-points projections provide title shares for all ten domestic leagues. Unchanged inputs skip retraining.

The optional Football-Data.co.uk weekly fixture CSV is validated, reconciled to known current-season clubs and cached for six hours. Its kickoff times are displayed as source times because the file does not provide a verified timezone. It is a short published window, not a full-season schedule; if the publisher serves an outdated file or no future rows, the existing data is kept and the app continues with its explicitly limited next-event fallback.

The tournament adapter loads five completed Champions League seasons (753 matches), the 2025 Club World Cup (64 matches), and the 2018, 2022 and 2026 World Cups (232 matches) from OpenFootball's CC0 repositories without an API key. All three competition families have stage, team, performance, scoring and match-result views. The World Cup view also uses 649 published goal events for scorer, penalty and own-goal analysis.

The 2026/27 campaign is integrated into every match-driven page and adds the Eredivisie, Primeira Liga, Belgian Pro League, Turkish Süper Lig and Greek Super League to the core five leagues. Overview shows the selected club's two nearest completed matches and next listed fixture when available; League tables reconstruct live partial standings; Club lab, Shot lab and Match explorer use the same current rows. The player explorer contains 458 tracked 2025/26 player records for the 12 clubs and 4,633 competition-season rows covering appearances, goals, assists, minutes and cards in 41 competitions. These come from the CC0 Transfermarkt Open Dataset, whose update pause and cutoff are visible in the interface. TheSportsDB remains an image and nearby-event fallback. The Catppuccin Mocha interface respects reduced-motion preferences. The app does not claim current 2026/27 squad accuracy, xG or possession.

## Structure

- `src/football_analysis/adapters.py`: remote public CSV and offline replay adapters, common interface, validation, retries and cache.
- `src/football_analysis/schema.sql`: SQL match table, ingestion audit and team-level analytical views.
- `src/football_analysis/ingest.py`: CLI, transactional partition replacement, checksum and failure audit.
- `src/football_analysis/pipeline.py` and `sync_state.py`: one incremental/bootstrap command and persisted freshness gates for rate-limited sources.
- `src/football_analysis/teams.py`: canonical provider-independent club labels and reconciliation keys.
- `src/football_analysis/recent.py`: current-season result and fixture synchronization for ten leagues.
- `src/football_analysis/fixtures.py`: guarded weekly fixture import and current-club reconciliation.
- `src/football_analysis/open_players.py`: featured-player aggregation plus normalized historical match context, event timelines, lineup roles and cup results from published CC0 CSVs.
- `src/football_analysis/players.py`: capped TheSportsDB profile and artwork fallback synchronization.
- `src/football_analysis/media.py`: cached club and competition artwork synchronization.
- `src/football_analysis/tournaments.py`: no-key CC0 Champions League, Club World Cup and World Cup adapters, cache and transactional synchronization.
- `src/football_analysis/analysis_system.py`: reusable filtering, ranking, form and correlation engine served through FastAPI.
- `src/football_analysis/event_details.py`: explicitly capped current-event enrichment from free TheSportsDB endpoints; Match Centre prefers the normalized historical Transfermarkt context, timeline and lineup tables when available.
- `src/football_analysis/prediction_features.py`: canonical match inputs and leakage-safe pre-match feature engineering.
- `src/football_analysis/predictions.py`: calibrated softmax fitting, chronological evaluation, model caching and fixture forecasts.
- `frontend/`: responsive Next.js and HeroUI application using the versioned FastAPI contracts.
- `docs/NEXTJS_READINESS.md`: completed frontend cutover and API contract status.
- `docs/NEXTJS_MIGRATION_PLAN.md`: phased FastAPI and Next.js cutover record with validation gates.
- `docs/SOURCE_CAPABILITY_AUDIT.md`: primary-source endpoint and dataset utilization audit.
- `docs/SOURCES.md`: source research and constraints.
- `docs/BACKLOG.md`: implementation tasks and next iterations.
- `tests/`: data-quality, idempotency and dashboard tests.

Data lives in `data/`; override with `FOOTBALL_DATA_DIR`. Raw archives and the database are excluded from version control. The lockfile pins the tested environment. No automated downloads run on page views.

## Verification

```bash
uv run pytest -q
cd frontend
npm run lint
npm run build
npx playwright install chromium
npm run test:e2e
```

See `docs/VALIDATION.md` for actual validation results and current coverage. Free access does not imply an unrestricted redistribution licence; retain attribution and review the source terms before distributing raw files or commercial deployment.
