# Next.js migration boundary

The Streamlit app is now a presentation layer over reusable Python and DuckDB modules. Tournament fetching and parsing live in `football_analysis.tournaments`; custom analysis lives behind `AnalysisSystem.build_report(AnalysisRequest)`. Neither module imports Streamlit.

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
- [x] `GET /api/v1/quality` — source caps, null coverage, checksums and refresh timestamps.

### Infrastructure

- [x] Read-only DuckDB connection pool with threading lock (`db.py`).
- [x] Cursor-based pagination for matches and players (`pagination.py`).
- [x] ETag headers derived from table checksums for conditional requests.
- [x] Cache-Control headers (15s for live data, 60s for stable snapshots).
- [x] CORS configured for Next.js dev server (`localhost:3000`).
- [x] Static OpenAPI v1 specification saved to [`docs/openapi_v1.json`](docs/openapi_v1.json).
- [x] Pydantic v2 response models with JSON serialization tests (`contracts.py`).
- [x] Canonical team IDs separate from display names (`teams.py`).

Keep DuckDB for this read-heavy, single-writer deployment. Run all synchronizers as separate jobs and open the app database read-only in the API process. Move to PostgreSQL only when concurrent writes or multiple API replicas require it.

## Next.js frontend shell status ✅

The frontend shell has been built in [`frontend/`](frontend/) with Next.js App Router, Tailwind CSS (Catppuccin Mocha tokens), and TanStack Query:

- [x] **Design Tokens**: Complete 26-color Catppuccin Mocha palette configured in [`frontend/src/app/globals.css`](frontend/src/app/globals.css).
- [x] **Navigation**: Responsive sidebar and mobile drawer with accessible toggle in [`frontend/src/components/navigation.tsx`](frontend/src/components/navigation.tsx). Covers all 9 dashboard areas.
- [x] **Typed API Client**: TypeScript types mirroring backend Pydantic models in [`frontend/src/lib/api/types.ts`](frontend/src/lib/api/types.ts) and centralized client in [`frontend/src/lib/api/client.ts`](frontend/src/lib/api/client.ts).
- [x] **State & Cache**: TanStack Query setup with SSR dehydration in [`frontend/src/lib/get-query-client.ts`](frontend/src/lib/get-query-client.ts) and query keys in [`frontend/src/lib/api/query-keys.ts`](frontend/src/lib/api/query-keys.ts).
- [x] **URL Filters**: Search params synchronization (`competition`, `season`, `team`, `venue`, `stage`, `metric`) via [`frontend/src/lib/hooks/use-filter-params.ts`](frontend/src/lib/hooks/use-filter-params.ts) and [`frontend/src/components/filters.tsx`](frontend/src/components/filters.tsx).
- [x] **UI Components**: `SourceBadge`, `LoadingSkeleton`, `ErrorMessage`, and `EmptyState` in [`frontend/src/components/ui/`](frontend/src/components/ui/).
- [x] **Overview Slice**: Initial overview page consuming `/api/v1/catalog` and `/api/v1/health` in [`frontend/src/app/page.tsx`](frontend/src/app/page.tsx).

## Feature Migration Slices (Phase 4) ✅

All core analytical views have been migrated to the Next.js frontend with full selector parity, interactive Recharts visualizations, and CSV export capabilities:

- [x] **Overview** ([`frontend/src/app/page.tsx`](frontend/src/app/page.tsx)): Real-time health indicator, KPI statistics, domestic league & tournament catalog cards.
- [x] **Champions League & World Cup** ([`frontend/src/app/tournaments/page.tsx`](frontend/src/app/tournaments/page.tsx)): Edition selector, stage scoring rates bar chart, match scorelines with penalty shootouts, top scorers ranking table, and CSV export.
- [x] **Analysis Lab** ([`frontend/src/app/analysis/page.tsx`](frontend/src/app/analysis/page.tsx)): Multi-metric rankings (PPG, GF, GA, Win %, Clean Sheet %, Form PPG), horizontal bar chart, form streak badges, in-match goals breakdown, referee disciplinary table, CSV export.
- [x] **Predictions** ([`frontend/src/app/predictions/page.tsx`](frontend/src/app/predictions/page.tsx)): Model card with accuracy & log-loss KPIs, upcoming match probability bars (Home/Draw/Away), and reliability calibration curve.
- [x] **League Tables** ([`frontend/src/app/tables/page.tsx`](frontend/src/app/tables/page.tsx)): Full domestic tables, European qualification & relegation indicators, home/away splits, goal difference, recent form streak, and CSV export.
- [x] **Club Lab** ([`frontend/src/app/clubs/page.tsx`](frontend/src/app/clubs/page.tsx)): Club selector, historical multi-season trajectory line chart, comprehensive season table, and recent club fixture results.
- [x] **Match Explorer** ([`frontend/src/app/matches/page.tsx`](frontend/src/app/matches/page.tsx)): Cursor-paginated match list, referee metadata, scorelines, search filter, and CSV export.
- [x] **Players** ([`frontend/src/app/players/page.tsx`](frontend/src/app/players/page.tsx)): Real-time search & cursor pagination, bio drawer, market valuation formatting in EUR, and historical career season statistics.
- [x] **Data Quality** ([`frontend/src/app/quality/page.tsx`](frontend/src/app/quality/page.tsx)): 60-cell competition completeness grid, source governance notes, null rate metrics, and SHA-256 ingestion audit logs.

The Next.js client should consume these routes rather than query DuckDB or reproduce football calculations. That keeps rankings and source semantics identical during the migration and allows Streamlit to remain available as a validation client until the replacement is complete.
