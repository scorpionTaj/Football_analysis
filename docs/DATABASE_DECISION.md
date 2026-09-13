# Database decision — 13 September 2026

## Decision

Keep **DuckDB** as the default database for the current Streamlit application. It is open source, embedded in the Python process, requires no server administration, reads compressed CSV directly and is designed for analytical SQL workloads. That matches a locally run, read-heavy portfolio dashboard with one ingestion writer and cached analytical tables.

Add **PostgreSQL** only when the application becomes a deployed multi-user service with concurrent ingestion, user accounts or multiple application workers. PostgreSQL is free and open source, ACID-compliant and uses MVCC so readers and writers can operate concurrently. Moving now would add a server, credentials, migrations and operations work without improving the current single-process experience.

| Need | DuckDB now | PostgreSQL later |
|---|---|---|
| Linux/local setup | One embedded database file | Separate server and configuration |
| Analytical scans and CSV ingestion | Excellent fit | Capable, with more loading/operations work |
| Streamlit read-only dashboard | Excellent fit | Good fit |
| Multiple concurrent writers/workers | Limited; coordinate one writer | Strong fit through server concurrency and MVCC |
| User accounts and row-level application data | Possible but awkward | Strong fit |
| Cost/licence | Free, open source | Free, PostgreSQL permissive licence |

Primary references:

- DuckDB explains its embedded, in-process architecture and OLAP focus: https://duckdb.org/why_duckdb
- PostgreSQL describes its open-source relational system: https://www.postgresql.org/about/
- PostgreSQL documents MVCC for multi-user concurrency: https://www.postgresql.org/docs/current/mvcc-intro.html
- PostgreSQL licence: https://www.postgresql.org/about/licence/

The schema remains portable SQL where practical. A future PostgreSQL adapter should be introduced behind the same repository/storage interface and validated with real concurrent workloads before replacing DuckDB.
