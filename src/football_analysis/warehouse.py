"""Run the dbt project (warehouse/) against the DuckDB file from Python callers."""

import os
import subprocess
import sys
from pathlib import Path

from .config import DATA, DB, ROOT

PROJECT = ROOT / "warehouse"


def build(db: Path = DB, select: str | None = None) -> dict:
    """`dbt build` (models + tests). Raises on any failing model or test."""
    env = {**os.environ, "FOOTBALL_DATA_DIR": str(DATA), "FOOTBALL_DUCKDB": str(Path(db).resolve())}
    command = [str(Path(sys.executable).with_name("dbt")), "build", "--project-dir", str(PROJECT),
               "--profiles-dir", str(PROJECT), *(["--select", select] if select else [])]
    result = subprocess.run(command, env=env, capture_output=True, text=True)
    summary = next((line for line in reversed(result.stdout.splitlines()) if "Done." in line), "")
    record_status(db)  # also after failures: the health page should show what broke
    if result.returncode:
        raise RuntimeError(f"dbt build failed: {summary or result.stdout[-2000:]}")
    return {"status": "success", "detail": summary.split("Done.")[-1].strip()}


LAYER_TABLES = {"marts": ["fct_match", "mart_team_season", "mart_dashboard_match", "fct_tournament_match",
                          "fct_tournament_goal", "dim_player", "fct_match_lineup"], "ml": ["ml_match_features", "model_runs"]}


def record_status(db: Path = DB) -> int:
    """Write dbt results, layer row counts and source freshness to main.pipeline_status."""
    import json
    from datetime import datetime

    import duckdb

    rows, now = [], datetime.now().replace(microsecond=0)
    results = PROJECT / "target" / "run_results.json"
    if results.exists():
        for item in json.loads(results.read_text())["results"]:
            kind, _, name = item["unique_id"].split(".", 2)
            rows.append(("dbt_" + kind, name.split(".")[-1], item["status"],
                         float(item["failures"] or 0), round(item["execution_time"], 3), (item["message"] or "")[:200]))
    with duckdb.connect(str(db)) as con:
        tables = {f"{s}.{t}" for s, t in con.execute(
            "SELECT table_schema, table_name FROM information_schema.tables").fetchall()}
        for schema, names in LAYER_TABLES.items():
            for name in names:
                if f"{schema}.{name}" in tables:
                    count = con.execute(f"SELECT count(*) FROM {schema}.{name}").fetchone()[0]
                    rows.append(("layer_rows", f"{schema}.{name}", "ok", float(count), None, ""))
        # Freshness = last successful check per source family (unchanged data still counts as checked).
        if "main.source_sync_cache" in tables:
            for name, latest in con.execute(
                    "SELECT split_part(source, ':', 1), max(synced_at) FROM main.source_sync_cache "
                    # completed seasons are immutable (bootstrap-only); prediction-model is the retired softmax key
                    "WHERE split_part(source, ':', 1) NOT IN ('historical-matches', 'prediction-model') GROUP BY 1").fetchall():
                rows.append(("freshness", name, "ok", (now - latest).total_seconds() / 3600, None, latest.isoformat()))
        con.execute("CREATE OR REPLACE TABLE main.pipeline_status (kind VARCHAR, name VARCHAR, status VARCHAR, "
                    "value DOUBLE, seconds DOUBLE, detail VARCHAR, checked_at TIMESTAMP)")
        con.executemany("INSERT INTO main.pipeline_status VALUES (?, ?, ?, ?, ?, ?, ?)", [(*r, now) for r in rows])
    return len(rows)


def main():
    import argparse
    import json

    parser = argparse.ArgumentParser(description="dbt build (models + data tests) on the DuckDB warehouse")
    parser.add_argument("--select", help="dbt node selection, e.g. fct_match+")
    print(json.dumps(build(select=parser.parse_args().select)))
