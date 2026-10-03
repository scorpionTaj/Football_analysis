#!/usr/bin/env bash
# Build the dbt warehouse (models + data tests) against a small checked-in fixture.
set -euo pipefail
root="$(cd "$(dirname "$0")/.." && pwd)"
work="$(mktemp -d)"
cp -r "$root/tests/fixtures/warehouse/raw" "$work/raw"
export FOOTBALL_DATA_DIR="$work" FOOTBALL_DUCKDB="$work/football.duckdb"
uv run python -c "from pathlib import Path; from football_analysis.ingest import connect; connect(Path('$work/football.duckdb')).close()"
uv run dbt build --project-dir "$root/warehouse" --profiles-dir "$root/warehouse"
