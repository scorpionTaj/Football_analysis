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
    if result.returncode:
        raise RuntimeError(f"dbt build failed: {summary or result.stdout[-2000:]}")
    return {"status": "success", "detail": summary.split("Done.")[-1].strip()}
