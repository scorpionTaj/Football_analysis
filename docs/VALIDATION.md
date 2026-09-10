# Validation — 10 September 2026

- Live public CSV ingestion: 25/25 league-season partitions succeeded.
- Matches loaded: 8,908 across five leagues and 2021/22–2025/26.
- Elite coverage: 60 club-season records (12 clubs × 5 seasons).
- Automated tests: 12 passed. Covers date rollover, eight corruption cases, repeat ingestion, failed refresh preservation, known-score calculations, NULL optional stats, dashboard filters and missing database.
- Real database Streamlit AppTest: 12 clubs, no coverage warning, no application exception.
- Connected browser: page, filters, metrics, season chart and comparison charts rendered; comparison tab navigation worked. No warning/error console entries were returned.
- Database validates completeness and internal consistency, not independent reconciliation against a second provider.
- Preferred agent-browser CLI was unavailable; visual verification used the connected in-app browser instead.

The working installation is /home/scorpiontaj/Projects/Football_analysis. The outputs copy contains the same source, documentation, lockfile and downloaded data as the initial deliverable; future development should use the working installation.
