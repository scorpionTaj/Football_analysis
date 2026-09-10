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
- [ ] FA-009 Add rolling five-match form and opponent-adjusted Elo, with chronological evaluation and no future leakage.
- [ ] FA-010 Add separate official standings adapter for deductions/tiebreakers. Acceptance: display results-derived and official points with distinct labels.
- [ ] FA-011 Add shot coverage indicators and efficiency analysis only where source coverage is sufficient.
- [ ] FA-012 Investigate a genuinely free, permitted player-season source. Acceptance: field coverage matrix for all 12 clubs and five seasons; no assumed assists/minutes.
- [ ] FA-013 Add player goals/assists/minutes/age only after FA-012 passes. Expose missingness rather than fill with invented values.

## Iteration 3 — packaging and operations
- [ ] FA-014 CI with offline tests, dependency updates and scheduled source availability checks.
- [ ] FA-015 Optional PostgreSQL deployment adapter when multi-user writing is needed.
- [ ] FA-016 Container and deployment guide after source redistribution/hosting terms review.
- [ ] FA-017 Optional StatsBomb event exploration with explicit partial coverage and required branding.

Tasks are local backlog items; no external issue tracker or recurring automation was created.
