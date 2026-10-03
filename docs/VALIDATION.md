# Validation — 3 October 2026

Current state of the checks. Earlier validation logs (Next.js cutover, PostgreSQL migration checkpoint,
softmax model audits) are in git history.

## Automated checks

| Check | Command | Result |
|---|---|---|
| Python unit, API and publish tests | `uv run pytest -q` | 100 passed, 1 opt-in skip (API tests build the serving marts with dbt) |
| dbt models + data tests, real warehouse | `uv run football-build-warehouse` | 118 nodes (29 models, 1 seed, 88 tests); 1 warn: 898 tournament goal events spell the club differently from the match record |
| dbt models + data tests, fixture data (CI) | `./scripts/ci_warehouse.sh` | 118/118 |
| Dagster definitions | `dagster definitions validate -m football_analysis.orchestration` | valid |
| Frontend | `npm run lint`, `tsc --noEmit`, `npm run build` | clean |
| Browser flows + accessibility | `npm run test:e2e` | 25/25, including axe WCAG A/AA scans of `/`, `/matches`, `/predictions`, `/settings`, `/models`, `/quality` in light and dark mode with no serious or critical violations |

The local PostgreSQL publish test starts a temporary server with `initdb`; it failed once and passed on every rerun, most likely a random-port collision.

## End-to-end checks (manual)

- `football-sync` (step 4) ran extract, dbt build, retraining and publishing with no failed sources. "Degraded" only reflects OpenFootball having no 2026/27 calendar for Belgium and Turkey.
- `football-publish` swapped only changed tables into Supabase (first run 26 s; unchanged tables skipped by row digest) and rebuilt the SQLite fallback (30 tables, ~1.39 M rows).
- API parity after moving queries onto the marts: 35 routes (catalog, teams, matches, tournaments, players, transfers, match detail, analysis, quality, overview…) returned identical JSON from the raw-table and mart queries on the real DuckDB snapshot.
- The API served `/api/v1/predictions` from Supabase, and from `data/football.sqlite3` when given an unreachable DSN.
- Retraining with unchanged inputs leaves `forecast_history` unchanged (journal only grows when probabilities move ≥ 1 point).

## Data snapshot

- Warehouse: 113,161 domestic matches, 15 leagues (top flights + five second divisions), 2005/06–2026/27; 75,414 with closing odds.
- Model features: 115,149 rows (played matches + upcoming fixtures).
- App tables: 25/25 dashboard league-seasons; ten live 2026/27 leagues; 335k timeline and 855k lineup rows from the Transfermarkt CC0 snapshot; 458 tracked players.
- Football-Data.co.uk had published results up to 20 September 2026 when checked on 3 October.
- Supabase private schema 337 MB of the 500 MB free tier (alert above 85%); large analytical tables stay in DuckDB.

## Model (walk-forward, 13,061 top-flight matches, last four completed seasons)

Champion ensemble: log loss 0.9670, RPS 0.1946, accuracy 53.4%, ECE 0.005. Bookmaker closing line:
0.954 / 0.1905 / 54.9%. See `MODELLING.md`.

## Known data issues handled by tests

Two federation-awarded cup results whose goal events exceed the official score (DFB-Pokal 2021 Münster–Wolfsburg, Copa del Rey 2023 Arosa–Granada; listed exceptions);
Ligue 1 2019/20 abandoned at 279 matches (documented exception); one Latin-1 source file (re-encoded on
landing); two broken closing-price rows (quarantined); provider club-name variants (reconciled by canonical key).

## Source constraints retained

- Live-season values remain explicitly partial.
- The open player snapshot stops before 2026/27 squad changes (upstream updates paused 6 July 2026).
- TheSportsDB event statistics, timelines and lineups remain explicitly capped samples.
- Full future fixture calendars are not claimed where no complete permitted source exists.
- Fixture-source check (3 October 2026): Greece imports from `openfootball/europe` (CC0 Football.TXT, 182 regular-season
  matches, 147 future, all 14 clubs reconciled). Belgium's CC0 file has all 306 pairings but only rounds 1–7 dated, so the
  date gate rejects it until the Pro League dates are added upstream. Turkey: no OpenFootball 2026/27 file; FixtureDownload
  has one but its terms allow personal, non-commercial use only, so it is not used.
- API-Football squads (optional, `API_FOOTBALL_KEY`): featured clubs only (~12 requests per full refresh, stop at the reserve),
  stored in `api_football_squads` with source URL and fetch time; not yet served by the API.
- Result-derived tables exclude administrative deductions and competition-specific tiebreak rules.
- Free access is not a redistribution licence: keep attribution and review terms before publishing raw files.
