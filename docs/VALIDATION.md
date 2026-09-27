# Validation — 23 September 2026

## PostgreSQL migration checkpoint — 27 September 2026

- The complete local DuckDB snapshot copied into a temporary PostgreSQL server, with every table content-verified before commit. Real-data API responses matched for catalog, 2026/27 matches, predictions, players, transfers and Champions League; the comparison exposed and fixed nondeterministic forecast ordering.
- The full suite passed: 107 tests, with the opt-in large snapshot test skipped on normal runs. The migration CLI installed and its help command ran successfully.
- The Supabase env file has a valid private schema and project-matching DSN, but its direct endpoint is IPv6-only and unreachable from this host. A session-pooler DSN is needed before remote validation or publication. DuckDB remains the writer and refresh backend.

## Final frontend cutover

- FastAPI is the only presentation data boundary; the Next.js/HeroUI application is the only frontend.
- The former nine-view workflow is covered by Overview, Tournaments, Analysis, League Tables, Club Lab, Shot Intelligence, Match Centre, Players and Data Quality. Predictions and Settings remain dedicated additional routes.
- Every listed Match Centre result now opens the unified detail contract. Stored statistics are used when present; historical matches use published managers, formations, named events and full lineup roles without synthesizing missing facts. Provider-only current matches keep an explicit partial-coverage label.
- Search inputs in navigation, matches, tournaments and players tolerate accents and small spelling mistakes.
- Settings exposes a four-step data-gathering depth control with one guarded backend refresh job and live status polling.
- Parity gaps closed before removal: external reference standings and deltas, complete quality counters and shot coverage, filtered tournament scorers and team performance, correlation rendering, player club/position facets and aggregates, actual listed fixtures without model coverage, rolling club form, percentile profile and newest-first match pagination.
- Backend verification covers route contracts, external standings reconciliation, player facets, quality telemetry, event details, named cards/goals/misses, lineup roles and listed-fixture fallback.
- Browser verification: Overview, League Tables, Analysis, Players, Tournaments, Club Lab and Data Quality rendered against the real database. New parity controls and sections were visible; player club/position filtering returned Arsenal attackers; tournament performance rendered 20 rows.
- Browser integrity: zero framework overlays, zero console errors and zero broken loaded images on the checked routes.
- Responsive check: 390 px viewport, 382 px document width, mobile navigation present and no horizontal overflow.
- Production gate: TypeScript, ESLint and the optimized Next.js build pass after contraction.

## Data snapshot

- Historical ingestion: 25/25 core league-season partitions.
- Live season: ten domestic competitions with 2026/27 partial results.
- Tournament catalog: Champions League, Europa League, Conference League, UEFA Super Cup, FA Cup, Carabao Cup, Community Shield, Copa del Rey, Supercopa, DFB-Pokal, Coppa Italia, KNVB Cup, Euros, Copa América, AFCON, Asian Cup, Club World Cup and World Cup, grouped by scope.
- Historical match detail: 335,270 verified timeline rows and 855,237 lineup rows from the open snapshot; 4,086 normalized cup matches.
- Player snapshot: 458 tracked players and 4,633 competition-season statistic rows from the published open dataset.
- Media cache: 414 team badges, with resilient initials or silhouette fallback when a provider has no usable image.
- Refresh performance: the six-file Transfermarkt importer rebuilt its existing snapshot in 38.7 seconds, then returned a cached result in 0.52 seconds on an unchanged rerun. Team artwork now commits every ten lookups and caches unavailable names for 30 days, so an interrupted all-team backfill resumes from saved work.
- Prediction model: 13 pre-match Elo/form/rest/shot features, chronological calibration and a 2,023-match holdout excluded from fitting and calibration. The earlier v3 model scored 51.4% accuracy and 0.997 log loss against a training-prevalence baseline of 43.2% and 1.075, improving on the previous 50.6% / 1.003 model on the same holdout. Shots on target were present for 99.98% of source matches. Its training took 7.9 seconds and an unchanged rerun returned from its input-fingerprint cache in 0.43 seconds. The holdout has now been used for development comparisons, so a fresh future-period audit is needed before claiming another out-of-sample improvement.
- Model improvement audit: adding venue-only rolling form marginally changed accuracy (51.41% to 51.46%) but worsened log loss (0.9970 to 0.9974), so it was removed. Five additional older seasons yielded 7,304 validated matches but also worsened the fixed later holdout slightly (0.9970 to 0.9974); they were not added to production training. Benchmarked histogram boosting, random forest and extra trees on the same chronological split; all had worse holdout log loss than the compact softmax, so no heavier dependency was added.
- Earlier selective prediction audit: a fixed 75% maximum-probability threshold selected 65 of 2,023 later holdout matches (3.2% coverage); 81.5% were correct, with a 95% Wilson interval of 70.4–89.1%. This was an observed narrow tier, not evidence that all fixtures can be predicted at 80%. The Predictions page shows coverage, uncertainty and per-league holdout results.
- Previous-season form experiment: explicit previous-season points-per-game and goal-difference features did not consistently improve forward-season log loss. Carrying the latest five actual matches into the next season's ten-match rolling form improved weighted walk-forward log loss from 0.9913 to 0.9873 across 7,609 games in 2022/23–2026/27; four seasons improved and one was effectively flat. This comparison selected the v4 feature and is exploratory, not an independent post-selection test. On the same 2,023-game chronological holdout, v4 scored 51.6% accuracy and 0.994 log loss versus v3's 51.4% and 0.997. The 75% confidence tier now contains 69 games (3.4% coverage), 78.3% correct with a 67.2–86.4% Wilson interval. There is no evidence of 80% accuracy across all fixtures.
- Subsequent reliability pass: the API no longer opens the production DuckDB file merely by importing its module. Refresh status is persisted with completed-stage checkpoints and interruption detection, while the UI accurately describes partial stage commits. Match Centre search now runs before pagination and detail state is encoded in a reloadable URL. Published forecasts have an additive history table; new model runs show per-outcome and season-by-season walk-forward diagnostics.
- Fixture source check on 23 September 2026: `https://www.football-data.co.uk/fixtures.csv` returned a valid 198-row CSV, but its latest match date was 20 September and it had zero future rows. The former `/matches/resources/fixtures.csv` path returned HTML. The weekly importer rejects stale/HTML responses without overwriting stored fixtures. The complementary OpenFootball importer passed a live isolated-DB check for seven complete 2026/27 calendars, storing 330 E0, 311 SP1, 270 D1, 330 I1, 261 F1, 243 N1 and 243 P1 future rows. All seven source club sets reconciled to current-season clubs; Belgium, Turkey and Greece had no current full files.
- Validation after this pass: all 87 Python tests passed when run with a normal worker-thread runtime; four Playwright Chromium flows passed for cross-page match search/deep links, 390 px navigation, refresh controls, prediction diagnostics and bounded full-calendar browsing. Frontend lint and production build passed. The sandboxed Python runner hangs even on a minimal synchronous FastAPI endpoint because AnyIO worker threads do not start there; use the unsandboxed test runtime or CI for the complete suite.
- Incremental sync: `football-sync` shares the frontend's four current-season stages; `--bootstrap` adds historical leagues, standings, tournaments and player snapshots. Twelve-hour OpenFootball schedule freshness, six-hour current CSV/standings/cup freshness, one-hour recent-event freshness, one-day event-detail freshness and seven-/30-day profile/stat freshness prevent repeated rate-limited requests. Checksums also skip unchanged partition writes and model retraining. Before the new full-calendar source was added, a live Premier League step-1 run took 10.7 seconds, then 0.59 seconds unchanged. A complete four-step scoped run succeeded, then repeated in 5.05 seconds with cached sources; those timings have not been remeasured for the new seven-file schedule path. The first bootstrap remains source-dependent; the caches accelerate subsequent runs.

## Source constraints retained

- Live-season values remain explicitly partial.
- The open player snapshot stops before current 2026/27 squad changes.
- TheSportsDB-only event statistics, timeline and lineup collections remain explicitly capped; complete historical snapshot rows are not subject to that API cap.
- Full future fixture calendars are not claimed where no complete permitted source is available.
- Result-derived tables exclude administrative deductions and competition-specific tiebreak rules; the external reference table exposes known differences where cached.

The working installation is `/home/scorpiontaj/Projects/Football_analysis`.
