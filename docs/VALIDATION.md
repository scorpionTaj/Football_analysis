# Validation — 14 September 2026

## Final frontend cutover

- FastAPI is the only presentation data boundary; the Next.js/HeroUI application is the only frontend.
- The former nine-view workflow is covered by Overview, Tournaments, Analysis, League Tables, Club Lab, Shot Intelligence, Match Centre, Players and Data Quality. Predictions and Settings remain dedicated additional routes.
- Parity gaps closed before removal: external reference standings and deltas, complete quality counters and shot coverage, filtered tournament scorers and team performance, correlation rendering, player club/position facets and aggregates, actual listed fixtures without model coverage, rolling club form, percentile profile and newest-first match pagination.
- Backend verification: 57 tests passed before removal, including route contracts, external standings reconciliation, player facets, quality telemetry, event details and listed-fixture fallback.
- Browser verification: Overview, League Tables, Analysis, Players, Tournaments, Club Lab and Data Quality rendered against the real database. New parity controls and sections were visible; player club/position filtering returned Arsenal attackers; tournament performance rendered 20 rows.
- Browser integrity: zero framework overlays, zero console errors and zero broken loaded images on the checked routes.
- Responsive check: 390 px viewport, 382 px document width, mobile navigation present and no horizontal overflow.
- Production gate: TypeScript, ESLint and the optimized Next.js build pass after contraction.

## Data snapshot

- Historical ingestion: 25/25 core league-season partitions.
- Live season: ten domestic competitions with 2026/27 partial results.
- Major tournaments: five Champions League seasons, the 2025 Club World Cup and three World Cup editions.
- Player snapshot: 458 tracked players and 4,633 competition-season statistic rows from the published open dataset.
- Media cache: 414 team badges, with resilient initials or silhouette fallback when a provider has no usable image.
- Prediction model: chronological calibration and untouched holdout evaluation; match forecasts and all ten domestic title outlooks are served from cached model tables.

## Source constraints retained

- Live-season values remain explicitly partial.
- The open player snapshot stops before current 2026/27 squad changes.
- Provider event statistics, timeline and lineup collections remain explicitly capped.
- Full future fixture calendars are not claimed where no complete permitted source is available.
- Result-derived tables exclude administrative deductions and competition-specific tiebreak rules; the external reference table exposes known differences where cached.

The working installation is `/home/scorpiontaj/Projects/Football_analysis`.
