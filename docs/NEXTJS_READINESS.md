# Next.js migration boundary

The Streamlit app is now a presentation layer over reusable Python and DuckDB modules. Tournament fetching and parsing live in `football_analysis.tournaments`; custom analysis lives behind `AnalysisSystem.build_report(AnalysisRequest)`. Neither module imports Streamlit.

Before replacing the interface, add a small read-only FastAPI service that owns the DuckDB connection and exposes these initial routes:

- `GET /competitions` — domestic leagues and tournaments with available seasons and freshness.
- `GET /teams?competition=&season=` — complete selectable team lists.
- `GET /matches?competition=&season=&team=&venue=&cursor=` — paginated normalized matches.
- `POST /analysis` — an `AnalysisRequest` body returning rankings, form, correlations and the applied filters.
- `GET /tournaments/{competition}/{season}` — stage summary and tournament results.
- `GET /players` and `GET /players/{id}` — paginated player discovery and existing profile/stat rows.

Keep DuckDB for this read-heavy, single-writer deployment. Run all synchronizers as separate jobs and open the app database read-only in the API process. Move to PostgreSQL only when concurrent writes or multiple API replicas require it.

The Next.js client should consume these routes rather than query DuckDB or reproduce football calculations. That keeps rankings and source semantics identical during the migration and allows Streamlit to remain available as a validation client until the replacement is complete.
