# Next.js migration plan

## Target architecture

Keep ingestion, source adapters, validation, DuckDB and football calculations in Python. Put a small read-oriented FastAPI service in front of `AnalysisSystem`, tournament queries and the prediction tables. The Next.js application becomes the presentation client and never reimplements ranking or model logic; its explicit refresh action pauses reads while the selected Python pipeline runs.

`Free sources → Python synchronizers → DuckDB → FastAPI v1 → Next.js App Router`

DuckDB remains appropriate while one scheduled job writes and one API process reads. Move to PostgreSQL only when multiple API replicas, concurrent writers or user-created persistent data require it.

## Phase 1 — freeze data contracts ✅

1. [x] Add Pydantic response models and JSON serialization tests for competitions, teams, matches, analysis reports, tournament results, players, predictions and quality metadata.
2. [x] Version the first API as `/api/v1`; expose source, coverage and freshness fields with every analytical response.
3. [x] Store canonical team IDs separately from user-facing names before URLs depend on club identity.
4. [x] Capture the former dashboard screens and baseline tests as the parity reference.

Exit gate: ✅ API schemas represent every dashboard view without a UI-framework dependency.

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
- [x] `GET /api/v1/standings` — results-derived rankings plus external reference deltas.

Infrastructure:

- [x] One application-owned read-only DuckDB connection pool with threading lock.
- [x] One guarded refresh coordinator closes and reopens that snapshot around the selected four-step write workflow.
- [x] Cursor pagination for large tables (matches, players).
- [x] ETags for stable snapshots derived from table checksums.
- [x] ETag-backed cache tiers (60s live, 5m stable, 24h historical) plus explicit active-query refresh in desktop and mobile navigation.
- [x] CORS configured for Next.js dev server (localhost:3000).
- [x] Synchronizers and model training stay outside request handlers.
- [x] Static OpenAPI v1 specification generated to `docs/openapi_v1.json`.

Exit gate: ✅ Contract tests and a generated OpenAPI document pass; p95 local response time stays below 300 ms for filtered analytical reads.

## Phase 3 — build the Next.js shell ✅

1. [x] Create a TypeScript Next.js App Router project with Catppuccin Mocha design tokens, responsive navigation and accessible filter components.
2. [x] Generate a typed API client from OpenAPI and centralize query keys, loading states, empty states and source/coverage labels.
3. [x] Implement route-level suspense boundaries and client components for interactive Recharts visualizations and selectors.
4. [x] Preserve shareable filter state in URLs: competition, season, team, stage, venue and metric.

Exit gate: ✅ Keyboard navigation, mobile layout, dark-theme contrast and error states pass before feature migration begins.

## Phase 4 — migrate by vertical slice ✅

Migrated in order with full selector parity, interactive Recharts, responsive Catppuccin Mocha cards, and CSV export parity:

1. [x] **Overview** (`/`): KPI cards (competitions, matches, season status), domestic vs tournament cards, API health check, source badges.
2. [x] **Champions League, Club World Cup and World Cup** (`/tournaments`): Tournament edition selector, stage scoring rates, match results with penalty shootouts, top scorers ranking table, and CSV export.
3. [x] **Analysis lab and predictions**:
   - [x] **Analysis lab** (`/analysis`): Multi-criteria rankings, horizontal bar chart, rolling form streak badges, in-match scoring factors, referee disciplinary impact, CSV export.
   - [x] **Predictions** (`/predictions`): calibrated 3-way outcome bars, untouched chronological holdout metrics, reliability evidence, CSV export and title probabilities for all ten domestic leagues.
4. [x] **League tables** (`/tables`): Full domestic standings with European qualification & relegation zones, home/away splits, goal difference, recent form, CSV export.
5. [x] **Club lab and Match explorer**:
   - [x] **Club lab** (`/clubs`): Multi-season trajectory line chart, historical seasons table, recent club fixture log, CSV export.
   - [x] **Match explorer** (`/matches`): Cursor-based pagination, referee metadata, scorelines, keyword filter, CSV export.
6. [x] **Players** (`/players`): Player discovery with search & cursor pagination, market valuations in EUR, bio information, and historical career season stats.
7. [x] **Data quality** (`/quality`): 60-cell competition completeness matrix, source governance notes, numerical column null rate KPIs, and SHA-256 ingestion audit logs.

Exit gate: ✅ API contract test, selector parity, empty-data behavior, download parity and matching metric totals verified across all 8 views.

## Phase 5 — multi-theme engine and settings ✅

1. [x] **Theme Engine**: 6 curated color themes (`mocha`, `latte`, `tokyo-night`, `nord`, `dracula`, `github-light`) mapped to Tailwind CSS v4 variables.
2. [x] **Theme Modes**: 3 operational modes (`auto` system media detection, `dark`, `light`) with `localStorage` persistence.
3. [x] **Settings Dashboard** (`/settings`): Live theme previews, mode toggles, pagination standard overview, and live API connectivity test.
4. [x] **Quick Switcher**: Integrated in navigation sidebar and header.

## Phase 6 — universal pagination standard ✅

1. [x] Standardize on 10 entries per page for all views displaying collections exceeding 10 rows.
2. [x] Reusable `<Pagination />` component with page numbers and ellipsis truncation.
3. [x] Applied across League Tables (`/tables`), Tournaments (`/tournaments`), Analysis Lab (`/analysis`), Club Lab (`/clubs`), Match Explorer (`/matches`), Player Profiles (`/players`), and Data Quality (`/quality`).

## Phase 7 — deep analytical integrations ✅

1. [x] **Head-to-Head Club Comparison** (`/clubs`): Direct clashes history, goals distribution bar, side-by-side PPG / Win % / Goals scored / Clean sheet benchmarking, and paginated match encounters.

## Phase 8 — extended media, multi-season expansion & overview revamp ✅

1. [x] **New Overview API Endpoint**: `GET /api/v1/overview` delivering spotlight club, 4 KPIs, latest match, previous match, next fixture with ML win probabilities, multi-season rankings, and season-end Elo progression.
2. [x] **Official Media & Badges Integration**:
   - `competition_media`: 12 competitions with official badge, logo, banner, trophy and fanart CDN assets.
   - `team_media`: Club and national-team badges/logos attached to `TeamRef` across all endpoints, with quota-aware missing-media sync and resilient UI fallback.
   - `open_players`: Transfermarkt player portraits with market valuation in EUR.
   - `<FootballBadge />`, `<CompetitionBadge />`, and `<PlayerAvatar />` with error handling and initials/silhouette fallbacks.
3. [x] **Multi-Season & Tournament Expansion**:
   - Champions League: 5 editions (2021, 2022, 2023, 2024, 2025).
   - World Cup: 3 editions (2018, 2022, 2026).
   - 10 Domestic Leagues: E0, SP1, D1, I1, F1 (2021–2026) + N1, P1, B1, T1, G1 (2026).
4. [x] **Revamped Overview Dashboard** (`/`):
   - HeroUI component system (`@heroui/react`) styling with glassmorphism and subtle animations.
   - Live Pulse indicator and 12-competition horizontal switcher.
   - Club spotlight hero with 4 KPIs (Played, W-D-L, PPG, Goal Difference).
   - 3 Match Strip Cards: Latest completed match, Previous match, Next listed fixture with ML win/draw/loss probability progress bars.
   - 4 parity analytical visualizations:
     1. Performance Over Time (PPG trajectory line chart)
     2. Season Strength Map (interactive heatmap matrix)
     3. Attacking Output vs Defensive Control (reversed scatter plot with PPG bubble size)
     4. Opponent-Adjusted Season-End Elo (progression line chart)
   - World Star Players Spotlight with Transfermarkt portraits, club badges, and market values.
   - 13 Supported Competitions card showcase, including the 2025 FIFA Club World Cup.

## Phase 9 — operations and cutover ✅

1. Run ingestion, event-detail refresh and prediction training as separate scheduled jobs with an atomic database snapshot swap.
2. Containerize FastAPI and Next.js separately; keep raw data and DuckDB outside the frontend image.
3. Add health checks, structured logs, source failure alerts and model-data freshness monitoring.
4. [x] Reconcile every former dashboard workflow against FastAPI contracts and browser-visible Next.js behavior.
5. [x] Add missing external standings, complete quality telemetry, tournament performance, filtered scorers, correlation rendering, player facets and listed-fixture fallback.
6. [x] Remove the retired Python UI entry point, UI-only tests and unused UI/chart dependencies.

Final cutover gate: ✅ API tests, production build, browser flows and metric reconciliation pass on the same data snapshot. The data model was unchanged; rollback remains a Git revert.
