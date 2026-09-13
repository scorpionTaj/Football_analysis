# football_analysis

Linux-friendly football analytics with Python, DuckDB, Plotly and Streamlit. No payment, API key, or subscription is required.

## Start

```bash
cd /home/scorpiontaj/Projects/Football_analysis
uv sync --extra dev
uv run football-ingest
uv run football-sync-standings
uv run football-sync-recent
uv run football-sync-players
uv run football-sync-open-players
uv run football-sync-media
uv run streamlit run app.py --server.address 127.0.0.1
```

Alternatively: create a Python 3.11+ virtual environment, run `pip install -e '.[dev]'`, then `football-ingest` and `streamlit run app.py`.

Open http://localhost:8501. Network is needed for the first download only. Use `uv run football-ingest --offline data/raw` for offline replay; `--refresh` redownloads archives. `--seasons 2024 --leagues E0` is useful for a small trial. Ingestion persists Elo and shot-efficiency analytics after committing source data; `uv run football-refresh-analytics` rebuilds only those caches. Failed partitions yield exit code 1 and appear in the source health panel; existing valid data remains intact. Stop ingestion before launching the dashboard (DuckDB uses a single writer).

## Scope

Real Madrid, FC Barcelona, Atlético Madrid, Manchester City, Liverpool, Arsenal, Bayern Munich, Borussia Dortmund, Paris Saint-Germain, Inter Milan, AC Milan and Juventus. All teams in their domestic leagues are ingested to preserve opponent context.

As of 10 September 2026 the target is 2021/22–2025/26. The July rollover selects five candidate completed seasons; each CSV must independently pass full double-round-robin coverage checks. A missing or unfinished season is visibly missing and never silently replaced by an older one.

Dashboard: platform-wide player/club/competition search, a Discover feature directory, analysis modes, season/competition/club filters, readable Top 5/10/all competition charts, results-derived tables, reconciled external top-five reference standings, season-aware rolling form, chronological Elo, coverage-gated shot efficiency, W/D/L, goals, clean sheets, trends, attack/defence comparison, match export and source health.

The current-season centre adds the Eredivisie, Primeira Liga, Belgian Pro League, Turkish Süper Lig and Greek Super League to the core five leagues. It combines completed public CSV results with the latest and next listed TheSportsDB event per competition. Select a competition and club to see the two nearest completed matches, current form, cumulative points, a partial results-derived table and the selected club's next listed fixture when available. The player explorer contains 458 tracked 2025/26 player records for the 12 clubs and 4,633 competition-season rows covering appearances, goals, assists, minutes and cards in 41 competitions. These come from the CC0 Transfermarkt Open Dataset, whose upstream update pause and 28 June 2026 match cutoff are visible in the interface. TheSportsDB remains an image fallback. The interface uses the Catppuccin Mocha palette across Streamlit controls, cards and Plotly charts. Motion respects the browser's reduced-motion preference. The app does not claim 2026/27 squad accuracy, xG or possession. Administrative points deductions appear as reference-versus-results adjustments.

## Structure

- `src/football_analysis/adapters.py`: remote public CSV and offline replay adapters, common interface, validation, retries and cache.
- `src/football_analysis/schema.sql`: SQL match table, ingestion audit and team-level analytical views.
- `src/football_analysis/ingest.py`: CLI, transactional partition replacement, checksum and failure audit.
- `src/football_analysis/teams.py`: canonical provider-independent club labels and reconciliation keys.
- `src/football_analysis/recent.py`: current-season result and fixture synchronization for ten leagues.
- `src/football_analysis/open_players.py`: full featured-club snapshot and five-season player aggregation from published CC0 CSVs.
- `src/football_analysis/players.py`: capped TheSportsDB profile and artwork fallback synchronization.
- `src/football_analysis/media.py`: cached club and competition artwork synchronization.
- `app.py`: dashboard (read-only database access).
- `docs/SOURCES.md`: source research and constraints.
- `docs/BACKLOG.md`: implementation tasks and next iterations.
- `tests/`: data-quality, idempotency and dashboard tests.

Data lives in `data/`; override with `FOOTBALL_DATA_DIR`. Raw archives and the database are excluded from version control. The lockfile pins the tested environment. No automated downloads run on page views.

## Verification

```bash
uv run pytest -q
```

See `docs/VALIDATION.md` for actual validation results and current coverage. Free access does not imply an unrestricted redistribution licence; retain attribution and review the source terms before distributing raw files or commercial deployment.
