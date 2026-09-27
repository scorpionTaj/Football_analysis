# Database decision — 13 September 2026

Status: this records the original DuckDB design. A user-requested PostgreSQL-only cutover is in progress; the verified snapshot copier is the first migration checkpoint, not a complete replacement.

## Decision

Keep **DuckDB** as the default database for the FastAPI analytical service. It is open source, embedded in the Python process, requires no server administration, reads compressed CSV directly and is designed for analytical SQL workloads. That matches a locally run, read-heavy platform with one ingestion writer and cached analytical tables.

Add **PostgreSQL** only when the application becomes a deployed multi-user service with concurrent ingestion, user accounts or multiple application workers. PostgreSQL is free and open source, ACID-compliant and uses MVCC so readers and writers can operate concurrently. Moving now would add a server, credentials, migrations and operations work without improving the current single-process experience.

| Need | DuckDB now | PostgreSQL later |
|---|---|---|
| Linux/local setup | One embedded database file | Separate server and configuration |
| Analytical scans and CSV ingestion | Excellent fit | Capable, with more loading/operations work |
| FastAPI read-only analytical service | Excellent fit | Good fit |
| Multiple concurrent writers/workers | Limited; coordinate one writer | Strong fit through server concurrency and MVCC |
| User accounts and row-level application data | Possible but awkward | Strong fit |
| Cost/licence | Free, open source | Free, PostgreSQL permissive licence |

Primary references:

- DuckDB explains its embedded, in-process architecture and OLAP focus: https://duckdb.org/why_duckdb
- PostgreSQL describes its open-source relational system: https://www.postgresql.org/about/
- PostgreSQL documents MVCC for multi-user concurrency: https://www.postgresql.org/docs/current/mvcc-intro.html
- PostgreSQL licence: https://www.postgresql.org/about/licence/

The schema remains portable SQL where practical. A future PostgreSQL adapter should be introduced behind the same repository/storage interface and validated with real concurrent workloads before replacing DuckDB.

## Optional match read model

DuckDB remains the canonical writer and default API store. PostgreSQL can hold a
published copy of one competition/season match partition for `/api/v1/matches`.
This is an opt-in read model, not a database migration.

Install the optional driver with `uv sync --extra postgres` (also use `--extra dev`
for tests). Provide a PostgreSQL DSN that can create the two `match_read_*`
tables and write rows, then publish each desired partition from a stable DuckDB
file:

```bash
export FOOTBALL_POSTGRES_DSN='postgresql://user:password@host:5432/football'
uv run --extra postgres football-publish-matches SP1 2024 --database data/football.duckdb
```

The publisher reads all four match sources, selects that partition, and stores
source rows plus a schema version, content version, row count, and SHA-256
checksum. It verifies the PostgreSQL copy before commit. Repeating an unchanged
publish leaves the content version intact; changed content advances it. A
transaction and partition lock keep a failed or concurrent publish invisible.
The API checks the version, row count, ordinal sequence, and checksum in one
repeatable-read snapshot before using the partition.

Tables are created in the private `football_analysis` schema by default, not
Supabase's Data API-exposed `public` schema. Set `FOOTBALL_POSTGRES_SCHEMA` to a
different private schema if needed. The database role needs permission to create
or use that schema; do not grant `anon` or `authenticated` access.

After publishing and checking parity in the target environment, enable scoped
reads with both settings:

```bash
export FOOTBALL_MATCH_READ_BACKEND=postgres
export FOOTBALL_POSTGRES_DSN='postgresql://user:password@host:5432/football'
```

Only requests with both `competition` and `season` use PostgreSQL. A missing,
damaged, or inaccessible partition returns 503; it is never served partially.
Unscoped requests and all other API routes continue to read DuckDB. Disable
the switch (or set it to `duckdb`) to roll back immediately; DuckDB data is not
changed or removed. Republish after ingestion, fixture updates, or source
changes. The published fixture slice is a snapshot, so schedule aging and live
refresh are not automatic. The PostgreSQL path still needs the DuckDB file for
team badges, API caching outside the scoped route, and other endpoints.
User accounts, analytical tables, Redis, and the frontend are outside this
read-model path.

For integration tests, set `TEST_POSTGRES_DSN` to a disposable local database,
or let pytest start a temporary PostgreSQL service when `initdb` and `pg_ctl`
are available. The tests create and remove a dedicated schema. Run
`uv run --extra dev --extra postgres pytest -q` to include these tests.
