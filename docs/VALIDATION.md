# Validation — 13 September 2026

- Live public CSV ingestion: 25/25 league-season partitions succeeded.
- Matches loaded: 8,908 across five leagues and 2021/22–2025/26.
- Elite coverage: 60 club-season records (12 clubs × 5 seasons).
- Automated tests: 22 passed. Covers date rollover, complete and partial-season normalization, corruption cases, repeat ingestion, failed refresh preservation, known-score calculations, NULL optional stats, canonical teams, player normalization, dashboard filters and missing database.
- Real database Streamlit AppTest: 12 clubs, no coverage warning, no application exception.
- Connected browser: page, filters, metrics, season chart and comparison charts rendered; comparison tab navigation worked. No warning/error console entries were returned.
- Iteration 2: 15 automated tests passed, including Elo chronology, same-day snapshot behavior, shot coverage, and the 95% metric gate.
- Real-data analytics: 17,816 Elo team-match rows from 8,908 fixtures; 484 eligible club-seasons for shot analysis, including all 60 selected elite club-seasons.
- External standings: 125 TheSportsDB reference rows; exactly five rows for each of 25 league-season partitions, matching the documented free-response cap.
- Streamlit test suite: eight tabs load against an isolated database with no application exception. A second-process AppTest against the live database is intentionally avoided while Streamlit owns DuckDB's read lock.
- Database validates completeness and internal consistency, not independent reconciliation against a second provider.
- Preferred agent-browser CLI was unavailable; visual verification used the connected in-app browser instead.
- Iteration 2.1: 19 automated tests passed, including canonical team identities, impossible-shot quarantine and persisted analytics.
- Real-data cache: 17,816 Elo rows and 484 shot-efficiency rows persisted for 8,908 matches; a cold in-process Elo rebuild previously took about 1.7 seconds.
- Data invariants: zero impossible shot rows remain. Two source matches have incomplete shot fields and are excluded by the 95% coverage gate.
- Standings reconciliation: all 125 reference rows map to the result-derived club identity. Nice 2021/22 is the sole points delta (reference 66, results 67), exposing the known one-point administrative adjustment.
- Iteration 2.2 current-season results: 336 completed matches across ten leagues, with source dates through 10 September 2026. Ten supplemental latest events bring the match-centre view to 346 deduplicated rows through 12 September 2026; ten next events are listed for 13 September 2026.
- Player sample: 120 profiles, exactly ten for each of the 12 elite clubs, plus 141 sparse historical statistic rows. Available types are appearances (75), goals (25), minutes played (22) and assists (19); absent values are not inferred.
- Connected browser: all ten recent competition choices rendered, the match-centre metrics showed 346 matches and a 12 September latest result, and the player selector rendered both an empty-stat state and Aurélien Tchouaméni's ten returned statistic rows.

The working installation is /home/scorpiontaj/Projects/Football_analysis. The outputs copy contains the same source, documentation, lockfile and downloaded data as the initial deliverable; future development should use the working installation.
