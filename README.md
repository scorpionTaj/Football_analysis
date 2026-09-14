# football_analysis

Linux-friendly football analytics with Python, DuckDB, Plotly and Streamlit. No payment, API key, or subscription is required.

## Start

```bash
cd /home/scorpiontaj/Projects/Football_analysis
uv sync --extra dev
uv run football-ingest
uv run football-sync-standings
uv run football-sync-recent
uv run football-sync-event-details
uv run football-sync-players
uv run football-sync-open-players
uv run football-sync-media
uv run football-sync-tournaments
uv run football-train-predictions
uv run football-api
uv run streamlit run app.py --server.address 127.0.0.1
```

Alternatively: create a Python 3.11+ virtual environment, run `pip install -e '.[dev]'`, then `football-ingest` and `streamlit run app.py`.

Open http://localhost:8501. Network is needed for the first download only. Use `uv run football-ingest --offline data/raw` for offline replay; `--refresh` redownloads archives. `--seasons 2024 --leagues E0` is useful for a small trial. Ingestion persists Elo and shot-efficiency analytics after committing source data; `uv run football-refresh-analytics` rebuilds only those caches. Failed partitions yield exit code 1 and appear in the source health panel; existing valid data remains intact. Stop ingestion before launching the dashboard (DuckDB uses a single writer).

## Scope

All 182 clubs currently present across the Premier League, La Liga, Bundesliga, Serie A, Ligue 1, Eredivisie, Primeira Liga, Belgian Pro League, Turkish Süper Lig and Greek Super League are selectable. Twelve elite clubs remain convenient defaults. UEFA Champions League and FIFA World Cup results are available through a separate tournament workflow.

The analytical range is 2021/22–2025/26 plus the live 2026/27 campaign. The July rollover selects five candidate completed seasons; each completed CSV must independently pass full double-round-robin coverage checks. Live rows are clearly labelled as partial and never presented as a completed season.

Dashboard: one platform-wide search, three domestic analysis modes and nine focused pages: Overview, Champions & World Cup, Analysis lab, League tables, Club lab, Shot lab, Match explorer, Players and Data quality. The Analysis lab slices domestic and tournament data by competition, edition, team and venue; ranks teams by seven metrics; builds a correlation matrix; analyzes first-half scoring, corners, fouls, cards and referee trends; and exports both the rankings and exact match slice.

The predictive section trains a regularized three-outcome softmax model on pre-match Elo, ten-match rolling points, scoring, conceding and rest-day features. Confidence temperature is learned from an earlier chronological calibration window; the latest 20% of match dates remain unseen during evaluation. The current model reaches 50.5% holdout accuracy versus a 42.9% majority-class baseline and improves log loss from 1.076 to 1.003. Ten next-listed fixtures are cached as home/draw/away probabilities, while conservative current-points projections provide title shares for all ten domestic leagues. This structured dataset is too small to justify a deep neural network; the compact model is faster, more auditable and easier to serve.

The tournament adapter loads five completed Champions League seasons (753 matches) and the 2018, 2022 and 2026 World Cups (232 matches) from OpenFootball's CC0 repositories without an API key. Champions League is the first tournament option and has stage, team, performance, scoring and match-result views. The World Cup view also uses 649 published goal events for scorer, penalty and own-goal analysis.

The 2026/27 campaign is integrated into every match-driven page and adds the Eredivisie, Primeira Liga, Belgian Pro League, Turkish Süper Lig and Greek Super League to the core five leagues. Overview shows the selected club's two nearest completed matches and next listed fixture when available; League tables reconstruct live partial standings; Club lab, Shot lab and Match explorer use the same current rows. The player explorer contains 458 tracked 2025/26 player records for the 12 clubs and 4,633 competition-season rows covering appearances, goals, assists, minutes and cards in 41 competitions. These come from the CC0 Transfermarkt Open Dataset, whose update pause and cutoff are visible in the interface. TheSportsDB remains an image and nearby-event fallback. The Catppuccin Mocha interface respects reduced-motion preferences. The app does not claim current 2026/27 squad accuracy, xG or possession.

## Structure

- `src/football_analysis/adapters.py`: remote public CSV and offline replay adapters, common interface, validation, retries and cache.
- `src/football_analysis/schema.sql`: SQL match table, ingestion audit and team-level analytical views.
- `src/football_analysis/ingest.py`: CLI, transactional partition replacement, checksum and failure audit.
- `src/football_analysis/teams.py`: canonical provider-independent club labels and reconciliation keys.
- `src/football_analysis/recent.py`: current-season result and fixture synchronization for ten leagues.
- `src/football_analysis/open_players.py`: full featured-club snapshot and five-season player aggregation from published CC0 CSVs.
- `src/football_analysis/players.py`: capped TheSportsDB profile and artwork fallback synchronization.
- `src/football_analysis/media.py`: cached club and competition artwork synchronization.
- `src/football_analysis/tournaments.py`: no-key CC0 Champions League, Club World Cup and World Cup adapters, cache and transactional synchronization.
- `src/football_analysis/analysis_system.py`: reusable filtering, ranking, form and correlation interface for Streamlit and a future HTTP/Next.js frontend.
- `src/football_analysis/event_details.py`: explicitly capped match statistics, timelines and lineup samples from the free TheSportsDB endpoints.
- `src/football_analysis/predictions.py`: leakage-aware feature engineering, softmax training, chronological evaluation and fixture forecasts.
- `app.py`: dashboard (read-only database access).
- `docs/NEXTJS_READINESS.md`: migration boundary and suggested API contract.
- `docs/NEXTJS_MIGRATION_PLAN.md`: phased FastAPI and Next.js cutover plan with validation gates.
- `docs/SOURCE_CAPABILITY_AUDIT.md`: primary-source endpoint and dataset utilization audit.
- `docs/SOURCES.md`: source research and constraints.
- `docs/BACKLOG.md`: implementation tasks and next iterations.
- `tests/`: data-quality, idempotency and dashboard tests.

Data lives in `data/`; override with `FOOTBALL_DATA_DIR`. Raw archives and the database are excluded from version control. The lockfile pins the tested environment. No automated downloads run on page views.

## Verification

```bash
uv run pytest -q
```

See `docs/VALIDATION.md` for actual validation results and current coverage. Free access does not imply an unrestricted redistribution licence; retain attribution and review the source terms before distributing raw files or commercial deployment.
