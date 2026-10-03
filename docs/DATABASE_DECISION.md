# Database decision

Decided 13 September 2026 (DuckDB), revised 3 October 2026 (current design below).

## Decision: DuckDB computes, PostgreSQL serves, SQLite is the fallback

| Store | Role | Written by | Read by |
|---|---|---|---|
| DuckDB `data/football.duckdb` | Single-writer warehouse: raw app tables, dbt layers, model outputs | extractors, `football-build-warehouse` (dbt), `football-train-models` | dbt, training, local API runs |
| PostgreSQL (Supabase, private schema `FOOTBALL_POSTGRES_SCHEMA`) | Serving copy for the API | `football-publish` only | FastAPI with `FOOTBALL_API_READ_BACKEND=postgres` |
| SQLite `data/football.sqlite3` | Read-only fallback | `football-publish` (rebuilt locally from DuckDB) | FastAPI when PostgreSQL is unreachable or no DSN is set |

Why:

- **One writer.** DuckDB allows a single writing process. Keeping every write there (extractors, dbt, training) avoids two sources of truth. The direct PostgreSQL writer pilot (`FOOTBALL_STORAGE_BACKEND=postgres` with an offline queue) was retired for this reason.
- **Analytics speed.** dbt models over 113k matches and Python feature building run on the local columnar engine. Doing that over a network database would be slower and would cost free-tier space.
- **Serving needs concurrency.** PostgreSQL (MVCC) lets the API read while new data is published, and it can be hosted. The API never opens DuckDB in this mode, so refreshes no longer pause reads.
- **Resilience.** The SQLite file keeps the app usable offline or during a Supabase outage.

## Publishing

`football-publish` (`src/football_analysis/publish.py`):

1. Computes a row digest for each served table in DuckDB and compares it with `snapshot_manifest` in the PostgreSQL schema.
2. Copies only changed tables to `<table>__next` with `COPY` and checks row counts.
3. In one transaction: drops the old tables, renames the new ones, recreates dependent views and updates the manifest. Readers see either the old or the new snapshot, never a mix.
4. Rebuilds the SQLite fallback in a temporary file from the same DuckDB tables, verifies counts, then renames it into place.

Served tables: every `main` app table plus `mart_team_season`, `model_runs` and `pipeline_status`.
Large analytical tables (`fct_match`, features, backtests) stay in DuckDB because the Supabase free tier
caps the database at 500 MB (≈ 458 MB used on 3 October 2026). Per-table swapping means peak extra space
is the size of the changed tables, not a second copy of the schema.

Security: the schema is private (not `public`), and neither `anon` nor `authenticated` has access. Keep
the DSN in the ignored `.env` (template: `.env.example`).

## Still present, scheduled for removal

The earlier per-partition match read model (`api/postgres_matches.py`, `football-publish-matches`,
`FOOTBALL_MATCH_READ_BACKEND`) still works, but `football-publish` supersedes it. Its removal is tracked in `BACKLOG.md`.

## References

- DuckDB architecture and concurrency: https://duckdb.org/why_duckdb, https://duckdb.org/docs/stable/connect/concurrency
- PostgreSQL MVCC: https://www.postgresql.org/docs/current/mvcc-intro.html
- Supabase database size limits: https://supabase.com/docs/guides/platform/database-size
