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

## Iteration 2.3 — visual identity and motion
- [x] FA-037 Cache official-style provider artwork for all 12 featured clubs and all 10 competitions.
- [x] FA-038 Add mode-aware hero branding for club focus and competition view.
- [x] FA-039 Add animated player cutouts, shirt-number watermark and a styled no-image fallback.
- [x] FA-040 Add club identity cards and competition badge rails.
- [x] FA-041 Respect reduced-motion preferences and keep the artwork layout responsive.
- [x] FA-042 Assess Free API Live Football Data on RapidAPI and retain the current multi-source architecture.
- [x] FA-043 Verify the redesigned overview, club focus, competition and player views in the live browser.

## Iteration 2.4 — complete player discovery
- [x] FA-044 Research current free/open squad and player-stat sources using primary documentation.
- [x] FA-045 Import all 458 tracked 2025/26 player records for the 12 featured clubs from the CC0 Transfermarkt snapshot.
- [x] FA-046 Aggregate 4,633 player competition-season rows across 2021/22–2025/26 without filling missing values.
- [x] FA-047 Add platform-wide search plus a Discover area for players, clubs, competitions and feature navigation.
- [x] FA-048 Add full-squad filters, player profiles, season charts, competition detail and squad totals.
- [x] FA-049 Record the source cutoff and keep the capped TheSportsDB feed as an artwork/profile fallback.
- [x] FA-050 Compare embedded DuckDB with PostgreSQL and retain DuckDB for the current single-process analytical app.
- [ ] FA-051 Add an optional API-Football current-squad adapter after a free key is configured and live 2026/27 coverage passes preflight checks.

## Iteration 2.5 — current season and Catppuccin interface
- [x] FA-052 Refresh all ten competitions with real 2026/27 completed results and nearby event data.
- [x] FA-053 Promote the current season to a clearly named primary navigation tab.
- [x] FA-054 Add selected-club latest match, previous match and next listed fixture cards.
- [x] FA-055 Add current form, points progression and a partial results-derived league table.
- [x] FA-056 Apply the Catppuccin Mocha palette to Streamlit controls, cards, tables and Plotly charts.
- [x] FA-057 Add current-season feature discovery and freshness indicators.
- [x] FA-058 Verify the current-season workflow, responsive visual hierarchy and browser console.
- [ ] FA-059 Add full fixture calendars only when a free source provides complete, permitted coverage; keep one-next-event labels explicit meanwhile.

## Iteration 2.6 — integrated live season and direct navigation
- [x] FA-060 Add 2026/27 to the shared season selector and every match-driven analytical page.
- [x] FA-061 Expand current results into team summaries and rebuild Elo and shot analytics from historical plus live matches.
- [x] FA-062 Expose all ten current competitions through the main competition selector and partial league tables.
- [x] FA-063 Move latest, previous and next-match context into Overview and label all current metrics as live partial data.
- [x] FA-064 Remove the redundant Discover and Current season pages; keep one search and seven focused pages.
- [x] FA-065 Verify the consolidated navigation, live calculations, tests and connected-browser rendering.

## Iteration 2.7 — tournament intelligence and analysis system
- [x] FA-066 Add a no-key CC0 adapter for five Champions League seasons and three FIFA World Cups.
- [x] FA-067 Promote Champions League and World Cup into a dedicated tournament page with stage, team and edition filters.
- [x] FA-068 Expose all 182 clubs found in the ten current domestic leagues through club focus, comparison and platform search.
- [x] FA-069 Add a reusable analysis system for filtering, rankings, recent form and metric correlations.
- [x] FA-070 Add a custom Analysis lab with domestic/tournament datasets, venue slices, metric rankings and CSV exports.
- [x] FA-071 Keep tournament and analysis logic independent of Streamlit and document the Next.js migration seam.
- [x] FA-072 Add parser, transaction, analysis-engine and nine-page dashboard tests.

## Iteration 2.8 — source utilization and predictive analysis
- [x] FA-075 Audit every active free source against its current first-party documentation and record used, newly used and intentionally excluded capabilities.
- [x] FA-076 Preserve first-half scores, corners, fouls, yellow/red cards and referees from Football-Data.co.uk.
- [x] FA-077 Add match-factor and referee analysis to the existing Analysis lab without another navigation page.
- [x] FA-078 Import World Cup scorer events, penalty flags and own-goal flags from the CC0 feed.
- [x] FA-079 Add explicitly capped TheSportsDB event-statistic, timeline and lineup sample adapters.
- [x] FA-080 Fix event refreshes when a provider ID moves from the upcoming collection into completed results.
- [x] FA-081 Add chronological pre-match feature engineering and a regularized three-outcome probability model.
- [x] FA-082 Publish holdout accuracy, log loss, Brier score, baseline comparisons, calibration and ten upcoming forecasts.
- [x] FA-083 Document why deep learning is deferred and complete a phased Next.js migration plan.

## Iteration 3 — packaging and operations
- [ ] FA-014 CI with offline tests, dependency updates and scheduled source availability checks.
- [ ] FA-015 Optional PostgreSQL deployment adapter when multi-user writing is needed.
- [ ] FA-016 Container and deployment guide after source redistribution/hosting terms review.
- [ ] FA-017 Optional StatsBomb event exploration with explicit partial coverage and required branding.
- [ ] FA-073 Add a read-only FastAPI layer over `AnalysisSystem` before starting the Next.js frontend.
- [ ] FA-074 Add cursor pagination and response-cache headers for match and player API routes.
- [ ] FA-084 Add a prediction retraining schedule only after the read-only API and ingestion job are deployed separately.

Tasks are local backlog items; no external issue tracker or recurring automation was created.
