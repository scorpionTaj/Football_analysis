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

The Next.js client should consume these routes rather than query DuckDB or reproduce football calculations. That keeps rankings and source semantics identical during the migration and allows Streamlit to remain available as a validation client until the replacement is complete.
