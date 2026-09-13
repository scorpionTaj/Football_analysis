# Task backlog

## Iteration 1 — working foundation
- [x] FA-001 Research free source constraints and choose a no-key historical source.
- [x] FA-002 Scaffold installable Python project and reproducible Linux environment.
- [x] FA-003 Implement remote CSV and offline replay adapters with caching/retries.
- [x] FA-004 Add DuckDB schema, result-derived analytics and ingestion audit.
- [x] FA-005 Add atomic, idempotent ingestion and complete-season validation.
- [x] FA-006 Build 12-club dashboard, comparison, filters, export and coverage health.
- [x] FA-007 Verify all 25 real league-season partitions; record gaps explicitly.
- [x] FA-008 Run automated validation and dashboard smoke tests.

## Iteration 2 — analytical depth
- [x] FA-018 Redesign season, competition and club selection around three analysis modes.
- [x] FA-019 Add reconstructed league tables with recent-form indicators.
- [x] FA-020 Add club form timelines, percentile profiles and opponent/venue match filters.
- [x] FA-021 Add a responsive performance heatmap and clearer source-health summary.
- [x] FA-009 Add rolling form and opponent-adjusted Elo with chronological evaluation and same-day snapshots to prevent leakage.
- [x] FA-010 Add a separate external standings adapter. TheSportsDB reference points are distinctly labelled; its free top-five cap is explicit.
- [x] FA-011 Add shot coverage indicators and a 95% gate for efficiency analysis.
- [x] FA-012 Investigate free, permitted player-season sources and publish the 12-club × five-season coverage matrix.
- [x] FA-013 Close the player feature gate without implementation: FA-012 did not pass, so missingness remains visible and no player values are inferred.

## Iteration 2.1 — trust and usability
- [x] FA-022 Keep competition charts readable with a single-league workflow and Top 5/10/All overview control.
- [x] FA-023 Synchronize Club focus across the club lab and match explorer; expose all league clubs in Competition view.
- [x] FA-024 Add provider-independent club identities and reconciled reference/result standings deltas.
- [x] FA-025 Reset rolling form at season boundaries and benchmark clean-sheet rate instead of raw totals.
- [x] FA-026 Quarantine impossible shots-on-target values and surface the invariant in Data quality.
- [x] FA-027 Make reference refreshes atomic and show reference/analytics refresh timestamps.
- [x] FA-028 Persist Elo and shot-efficiency analytics after ingestion to reduce dashboard startup work.
- [x] FA-029 Expand automated and browser verification for the new modes, analytics cache and data-quality rules.

## Iteration 2.2 — recent coverage and player explorer
- [x] FA-030 Add a current-season match centre for ten European domestic competitions.
- [x] FA-031 Combine completed Football-Data.co.uk results with the latest and next TheSportsDB event per competition.
- [x] FA-032 Support incomplete current-season CSV partitions without weakening completed-season validation.
- [x] FA-033 Add per-player profiles for all 12 elite clubs through the capped TheSportsDB free feed.
- [x] FA-034 Display source-returned goals, assists, appearances and minutes without filling missing values.
- [x] FA-035 Add recent/player freshness and coverage to Data quality.
- [x] FA-036 Verify recent competition selection and populated/empty player states in the live browser.

## Iteration 3 — packaging and operations
- [ ] FA-014 CI with offline tests, dependency updates and scheduled source availability checks.
- [ ] FA-015 Optional PostgreSQL deployment adapter when multi-user writing is needed.
- [ ] FA-016 Container and deployment guide after source redistribution/hosting terms review.
- [ ] FA-017 Optional StatsBomb event exploration with explicit partial coverage and required branding.

Tasks are local backlog items; no external issue tracker or recurring automation was created.
