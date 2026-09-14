# Next.js cutover status

The responsive Next.js/HeroUI client is the only application frontend. Tournament fetching and parsing live in `football_analysis.tournaments`; custom analysis lives behind `AnalysisSystem.build_report(AnalysisRequest)` and every UI read crosses FastAPI v1.

## API service status ✅

A read-only FastAPI service now owns the DuckDB connection and exposes all initial routes under `/api/v1`. The implementation lives in [`src/football_analysis/api/`](src/football_analysis/api/) with full test coverage in [`tests/test_api.py`](tests/test_api.py) and [`tests/test_api_contracts.py`](tests/test_api_contracts.py).

### Implemented routes

- [x] `GET /api/v1/catalog` — competitions, seasons, coverage and source freshness.
- [x] `GET /api/v1/teams?competition=&season=` — complete selectable team lists.
- [x] `GET /api/v1/matches?competition=&season=&team=&venue=&cursor=` — paginated normalized matches.
- [x] `POST /api/v1/analysis` — an `AnalysisRequest` body returning rankings, form, correlations and the applied filters.
- [x] `GET /api/v1/tournaments/{competition}/{season}` — stage summary and tournament results.
- [x] `GET /api/v1/players` and `GET /api/v1/players/{player_id}` — paginated player discovery and existing profile/stat rows.
- [x] `GET /api/v1/predictions` — model card, holdout metrics, calibration and current forecasts.
- [x] `GET /api/v1/shots` — shot coverage and efficiency behind a 95% quality gate.
- [x] `GET /api/v1/event-details` and `GET /api/v1/event-details/{event_id}` — cached event summaries, statistics, timeline and lineup samples.
- [x] `GET /api/v1/overview` and `GET /api/v1/transfers` — dashboard spotlight and transfer showcase data.
- [x] `GET /api/v1/quality` — source caps, null coverage, checksums and refresh timestamps.
- [x] `GET /api/v1/standings` — results table, reference table and reconciliation deltas.

### Infrastructure

- [x] Read-only DuckDB connection pool with threading lock (`db.py`).
- [x] Cursor-based pagination for matches and players (`pagination.py`).
- [x] ETag headers derived from table checksums for conditional requests.
- [x] Cache-Control headers (60s live, 5m stable, 24h historical) with stale-while-revalidate.
- [x] CORS configured for Next.js dev server (`localhost:3000`).
- [x] Static OpenAPI v1 specification saved to [`docs/openapi_v1.json`](docs/openapi_v1.json).
- [x] Pydantic v2 response models attached to every route and included in the generated OpenAPI document.
- [x] Canonical team IDs separate from display names (`teams.py`).

Keep DuckDB for this read-heavy, single-writer deployment. Run all synchronizers as separate jobs and open the app database read-only in the API process. Move to PostgreSQL only when concurrent writes or multiple API replicas require it.

## Next.js frontend shell status ✅

The frontend shell has been built in [`frontend/`](frontend/) with Next.js App Router, Tailwind CSS (Catppuccin Mocha tokens), and TanStack Query:

- [x] **Design Tokens**: Complete 26-color Catppuccin Mocha palette configured in [`frontend/src/app/globals.css`](frontend/src/app/globals.css).
- [x] **Navigation**: Responsive modern sidebar/mobile dock, active-query refresh and cross-platform club/player/competition search in [`frontend/src/components/navigation.tsx`](frontend/src/components/navigation.tsx). Covers all 11 dashboard routes.
- [x] **Typed API Client**: TypeScript types mirroring backend Pydantic models in [`frontend/src/lib/api/types.ts`](frontend/src/lib/api/types.ts) and centralized client in [`frontend/src/lib/api/client.ts`](frontend/src/lib/api/client.ts).
- [x] **State & Cache**: TanStack Query setup with SSR dehydration in [`frontend/src/lib/get-query-client.ts`](frontend/src/lib/get-query-client.ts) and query keys in [`frontend/src/lib/api/query-keys.ts`](frontend/src/lib/api/query-keys.ts).
- [x] **URL Filters**: Search params synchronization (`competition`, `season`, `team`, `venue`, `stage`, `metric`) via [`frontend/src/lib/hooks/use-filter-params.ts`](frontend/src/lib/hooks/use-filter-params.ts) and [`frontend/src/components/filters.tsx`](frontend/src/components/filters.tsx).
- [x] **UI Components**: `SourceBadge`, `LoadingSkeleton`, `ErrorMessage`, and `EmptyState` in [`frontend/src/components/ui/`](frontend/src/components/ui/).
- [x] **Overview Slice**: Initial overview page consuming `/api/v1/catalog` and `/api/v1/health` in [`frontend/src/app/page.tsx`](frontend/src/app/page.tsx).

## Feature Migration Slices (Phase 4) ✅

All core analytical views have been migrated to the Next.js frontend with full selector parity, interactive Recharts visualizations, and CSV export capabilities:

- [x] **Overview** ([`frontend/src/app/page.tsx`](frontend/src/app/page.tsx)): Real-time health indicator, KPI statistics, domestic league & tournament catalog cards.
- [x] **Champions League, Club World Cup & World Cup** ([`frontend/src/app/tournaments/page.tsx`](frontend/src/app/tournaments/page.tsx)): Edition/stage/team selectors, selected-slice scoring rates, match scorelines with shootouts, filtered scorer table, team performance ranking and CSV export.
- [x] **Analysis Lab** ([`frontend/src/app/analysis/page.tsx`](frontend/src/app/analysis/page.tsx)): Multi-metric rankings, horizontal bar chart, form streak badges, correlation matrix, match factors, referee disciplinary table and CSV export.
- [x] **Predictions** ([`frontend/src/app/predictions/page.tsx`](frontend/src/app/predictions/page.tsx)): calibrated match probabilities, holdout metrics, reliability evidence and title outlooks for every domestic league.
- [x] **League Tables** ([`frontend/src/app/tables/page.tsx`](frontend/src/app/tables/page.tsx)): Full domestic tables, home/away splits, goal difference, recent form, external reference table and administrative/rank deltas.
- [x] **Club Lab** ([`frontend/src/app/clubs/page.tsx`](frontend/src/app/clubs/page.tsx)): Club selector, configurable rolling form, percentile profile, historical trajectory/table, recent results and head-to-head comparison.
- [x] **Match Explorer** ([`frontend/src/app/matches/page.tsx`](frontend/src/app/matches/page.tsx)): Cursor-paginated match list, referee metadata, scorelines, search filter, and CSV export.
- [x] **Players** ([`frontend/src/app/players/page.tsx`](frontend/src/app/players/page.tsx)): Name/team/position/nationality search, club and position facets, squad summaries, bio drawer, season aggregates and complete competition rows.
- [x] **Data Quality** ([`frontend/src/app/quality/page.tsx`](frontend/src/app/quality/page.tsx)): Coverage matrix, all source counters, refresh timestamps, shot coverage, governance notes, null rates and SHA-256 ingestion history.

## Phase 5: Multi-Theme Engine & Settings Dashboard ✅

A complete customization and theme system has been implemented across the application:
- [x] **Theme Engine**: 6 distinct curated color themes (`mocha`, `latte`, `tokyo-night`, `nord`, `dracula`, `github-light`) spanning dark and light modes.
- [x] **Theme Modes**: 3 operational modes (`auto` system detection via `prefers-color-scheme`, force `dark`, and force `light`).
- [x] **Persistence**: Client `localStorage` caching with zero hydration mismatch warnings.
- [x] **Settings Page** ([`frontend/src/app/settings/page.tsx`](frontend/src/app/settings/page.tsx)): Interactive palette cards with live swatch previews, mode toggles, pagination standard overview, and live API connectivity test.
- [x] **Quick Switcher**: Integrated in both desktop sidebar and mobile navigation header.

## Phase 6: Universal Pagination (10 Entries Standard) ✅

In accordance with dashboard usability standards, all views displaying collections greater than 10 rows enforce 10-entries-per-page pagination:
- [x] **Reusable Pagination Infrastructure**: Accessible `<Pagination />` component with page numbers, ellipsis collapse, and `usePagination(items, pageSize = 10)` hook.
- [x] **League Tables** (`/tables`): Standings table paginated at 10 clubs per page.
- [x] **Tournaments** (`/tournaments`): Matches list paginated at 10/page and Top Scorers paginated at 10/page.
- [x] **Analysis Lab** (`/analysis`): Metric rankings table paginated at 10 teams per page.
- [x] **Club Lab** (`/clubs`): Historical multi-season records (10/page), recent fixtures (10/page), and Head-to-Head direct encounters (10/page).
- [x] **Match Explorer** (`/matches`): Cursor pagination set to 10 fixtures per page.
- [x] **Players** (`/players`): Player discovery cursor list (10/page) and player career stats table (10/page).
- [x] **Data Quality** (`/quality`): Ingestion checksums and audit records paginated at 10/page.

## Phase 7: Deep Analytical Integrations ✅

- [x] **Head-to-Head Club Comparison** ([`frontend/src/app/clubs/page.tsx`](frontend/src/app/clubs/page.tsx)): Toggle between individual Club Profile and direct Head-to-Head comparison between any two clubs. Includes direct clashes record, goals distribution bar, side-by-side PPG / Win % / Goals scored / Clean sheet benchmarking, and paginated match encounters.

## Phase 8: Extended Media, Multi-Season Expansion & Revamped Overview ✅

- [x] **New Overview API Endpoint**: `GET /api/v1/overview?team=&competition=&season=` exposing spotlight club, 4 KPIs, latest match, previous match, upcoming ML forecast, full season-by-season rankings, and opponent-adjusted Elo progression.
- [x] **Official Media & Badges Integration**:
  - Direct CDN crests & logos for supported competitions (`competition_media`).
  - Club crests and emblems for all domestic and tournament clubs (`team_media`).
  - Transfermarkt player portraits with market valuation in EUR (`open_players`).
  - Fallback `<FootballBadge />`, `<CompetitionBadge />`, and `<PlayerAvatar />` components in [`frontend/src/lib/media-utils.tsx`](frontend/src/lib/media-utils.tsx).
- [x] **Multi-Season & Tournament Expansion**:
  - UEFA Champions League: Unlocked 5 complete editions (2021, 2022, 2023, 2024, 2025).
  - FIFA World Cup: Unlocked 3 tournament editions (2018, 2022, 2026).
  - FIFA Club World Cup: all 64 completed matches from the 2025 edition.
  - 10 Domestic Leagues: E0, SP1, D1, I1, F1 (2021–2026), plus N1 (Eredivisie), P1 (Primeira Liga), B1 (Belgian Pro League), T1 (Turkish Süper Lig), G1 (Greek Super League) (live 2026).
- [x] **Revamped Overview Dashboard** ([`frontend/src/app/page.tsx`](frontend/src/app/page.tsx)):
  - Live pulse header and horizontal 13-competition switcher rail.
  - Club spotlight hero with 4 KPIs (Matches, W-D-L, PPG, Goal Difference).
  - 3 match strip cards: Latest completed match, Previous match, Next listed fixture with ML win/draw/loss probability bars.
  - 4 parity analytical visualizations:
    1. **Performance Over Time**: PPG line chart across seasons.
    2. **Season Strength Map**: Heatmap matrix showing PPG per season for top clubs.
    3. **Attacking Output vs Defensive Control**: Reversed scatter plot (Goals/match vs Conceded/match) with bubble size = PPG.
    4. **Opponent-Adjusted Season-End Elo**: Chronological Elo progression across domestic seasons.
  - Star Players Spotlight showcasing world-class players with portraits and market values.
  - Supported Tournaments & Domestic Leagues 13-card showcase.
- [x] **HeroUI Integration**:
  - `@heroui/react` 3.2.5 components (Card, Chip, Avatar, Badge, Button, Tabs, Tooltip).
  - Enhanced glassmorphic styles and custom smooth animations.

The cutover is complete. The Next.js client consumes these routes rather than query DuckDB or reproduce football calculations. The retired client, its UI tests, and its UI-only dependencies have been removed after API tests and connected-browser parity checks passed.
