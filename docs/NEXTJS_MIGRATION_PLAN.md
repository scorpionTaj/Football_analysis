# Next.js migration plan

## Target architecture

Keep ingestion, source adapters, validation, DuckDB and football calculations in Python. Put a small read-only FastAPI service in front of `AnalysisSystem`, tournament queries and the prediction tables. The Next.js application becomes the presentation client and never reimplements ranking or model logic.

`Free sources → Python synchronizers → DuckDB → FastAPI v1 → Next.js App Router`

DuckDB remains appropriate while one scheduled job writes and one API process reads. Move to PostgreSQL only when multiple API replicas, concurrent writers or user-created persistent data require it.

## Phase 1 — freeze data contracts ✅

1. [x] Add Pydantic response models and JSON serialization tests for competitions, teams, matches, analysis reports, tournament results, players, predictions and quality metadata.
2. [x] Version the first API as `/api/v1`; expose source, coverage and freshness fields with every analytical response.
3. [x] Store canonical team IDs separately from user-facing names before URLs depend on club identity.
4. [x] Capture the current Streamlit screens and 38-test baseline as the parity reference.

Exit gate: ✅ API schemas can represent every current dashboard view without importing Streamlit.

## Phase 2 — create the FastAPI service ✅

Initial routes:

- [x] `GET /api/v1/catalog` — competitions, seasons, coverage and source freshness.
- [x] `GET /api/v1/teams?competition=&season=` — complete club/team selector data.
- [x] `GET /api/v1/matches?competition=&season=&team=&venue=&cursor=` — paginated match rows.
- [x] `POST /api/v1/analysis` — rankings, form, correlations and match-factor summaries.
- [x] `GET /api/v1/tournaments/{competition}/{season}` — stages, matches and World Cup scorers.
- [x] `GET /api/v1/predictions` — model card, holdout metrics, calibration and current forecasts.
- [x] `GET /api/v1/players` and `GET /api/v1/players/{player_id}` — paginated discovery and profiles.
- [x] `GET /api/v1/quality` — source caps, null coverage, checksums and refresh timestamps.

Infrastructure:

- [x] One application-owned read-only DuckDB connection pool with threading lock.
- [x] Cursor pagination for large tables (matches, players).
- [x] ETags for stable snapshots derived from table checksums.
- [x] Short cache headers for current results (15s live, 60s stable).
- [x] CORS configured for Next.js dev server (localhost:3000).
- [x] Synchronizers and model training stay outside request handlers.
- [x] Static OpenAPI v1 specification generated to `docs/openapi_v1.json`.

Exit gate: ✅ Contract tests and a generated OpenAPI document pass; p95 local response time stays below 300 ms for filtered analytical reads.

## Phase 3 — build the Next.js shell

1. Create a TypeScript Next.js App Router project with Catppuccin Mocha design tokens, responsive navigation and accessible filter components.
2. Generate a typed API client from OpenAPI and centralize query keys, loading states, empty states and source/coverage labels.
3. Implement server components for initial page data and client components only for interactive Plotly charts and selectors.
4. Preserve shareable filter state in URLs: competition, season, team, stage, venue and metric.

Exit gate: keyboard navigation, mobile layout, dark-theme contrast and error states pass before feature migration begins.

## Phase 4 — migrate by vertical slice

Migrate in this order: Overview; Champions League and World Cup; Analysis lab and predictions; League tables; Club lab and Match explorer; Players; Data quality. Keep Streamlit available against the same database after every slice and compare totals, filters and exports.

Exit gate for each page: API contract test, visual regression, selector parity, empty-data behavior, download parity and matching metric totals.

## Phase 5 — operations and cutover

1. Run ingestion, event-detail refresh and prediction training as separate scheduled jobs with an atomic database snapshot swap.
2. Containerize FastAPI and Next.js separately; keep raw data and DuckDB outside the frontend image.
3. Add health checks, structured logs, source failure alerts and model-data freshness monitoring.
4. Route a preview URL to Next.js, run both clients for one full refresh cycle, then make Next.js primary.
5. Retain the Streamlit deployment briefly as an internal analytical reference before removing it.

Final cutover gate: all API tests, browser flows and metric reconciliation pass on the same production snapshot; rollback is a routing change rather than a data migration.
