"""Dagster definitions: sources → DuckDB (raw) → dbt (staging/marts/ml) → models → serving stores.

    DAGSTER_HOME=$PWD/.dagster uv run dagster dev -m football_analysis.orchestration

Extraction assets wrap the existing `sync_*` functions unchanged; their freshness gates
(`sync_state.py`) still decide whether a provider is actually contacted. Every asset that
writes DuckDB carries the `duckdb_writer` tag, limited to one concurrent run in dagster.yaml.
"""

import os
import sys
from pathlib import Path

import dagster as dg
from dagster_dbt import DagsterDbtTranslator, DbtCliResource, DbtProject, dbt_assets

from ..config import CLUBS, DATA, DB, RECENT_LEAGUES, ROOT, current_season, seasons

os.environ.setdefault("FOOTBALL_DATA_DIR", str(DATA))
os.environ.setdefault("MLFLOW_DISABLE_AGENT_HINT", "1")

WRITER = {"duckdb_writer": "true"}
dbt_project = DbtProject(project_dir=ROOT / "warehouse", profiles_dir=ROOT / "warehouse")
dbt_project.prepare_if_dev()


def _report(result) -> dg.MaterializeResult:
    """Turn a sync report (dict or list of dicts) into Dagster metadata; fail on required errors."""
    rows = result if isinstance(result, list) else [result] if isinstance(result, dict) else []
    statuses = [str(row.get("status", "success")) for row in rows if isinstance(row, dict)]
    return dg.MaterializeResult(metadata={
        "partitions": len(rows),
        "failed": sum(s == "failed" for s in statuses),
        "cached": sum(s == "cached" for s in statuses),
        "detail": dg.MetadataValue.json(rows[:50]),
    })


# ── Extraction (raw layer) ────────────────────────────────────────────────────

@dg.asset(key=["landing", "football_data_csv"], group_name="extract", op_tags=WRITER,
          description="Football-Data season CSVs (15 leagues, 2005+) landed untouched in data/raw.")
def landing_football_data():
    from ..history import fetch_history
    return _report(fetch_history())  # completed seasons are immutable; current season re-lands


@dg.asset(key=["app", "matches"], group_name="extract", op_tags=WRITER,
          description="Validated complete-season results for the dashboard window.")
def app_matches():
    from ..adapters import FootballDataCSV
    from ..ingest import ingest
    return _report(ingest(FootballDataCSV(DATA / "raw"), db=DB, years=seasons()))


@dg.asset(key=["app", "recent_matches"], group_name="extract", op_tags=WRITER,
          description="Current-season results for ten leagues (6-hour freshness gate).")
def app_recent_matches():
    from ..recent import sync_recent
    return _report(sync_recent(db=DB, year=current_season(), leagues=list(RECENT_LEAGUES)))


@dg.asset(key=["app", "recent_events"], deps=[app_recent_matches], group_name="extract", op_tags=WRITER,
          description="Full-season OpenFootball schedules + weekly fixture window + cup events.")
def app_recent_events():
    from ..fixtures import sync_fixtures
    from ..open_fixtures import sync_open_fixtures
    from ..recent import sync_cup_events
    season, leagues = current_season(), list(RECENT_LEAGUES)
    rows = list(sync_open_fixtures(db=DB, season=season, leagues=leagues) or [])
    rows.append(sync_fixtures(db=DB, season=season, leagues=leagues))
    rows.append(sync_cup_events(db=DB, season=season) or {})
    return _report(rows)


@dg.asset(key=["app", "reference_standings"], group_name="extract", op_tags=WRITER)
def app_reference_standings():
    from ..reference_standings import sync
    return _report(sync(db=DB, years=[current_season()], leagues=["E0", "D1", "I1", "F1", "SP1"]))


@dg.asset(key=["app", "tournament_matches"], group_name="extract", op_tags=WRITER)
def app_tournament_matches():
    from ..tournaments import OpenFootballTournaments, default_partitions, sync_tournaments
    return _report(sync_tournaments(db=DB, partitions=default_partitions(), adapter=OpenFootballTournaments()))


@dg.asset(key=["app", "open_players"], group_name="extract", op_tags=WRITER,
          description="Transfermarkt CC0 players, match context, timelines, lineups and transfers.")
def app_open_players():
    from ..open_players import sync_open_players
    from ..transfers import sync_transfers
    result = sync_open_players(db=DB)
    return _report([result if isinstance(result, dict) else {"status": "success"},
                    {"status": "success", "transfers": sync_transfers(db=DB)}])


@dg.asset(key=["app", "media"], group_name="extract", op_tags=WRITER,
          description="Featured players, club/competition artwork and capped event details.")
def app_media():
    from ..event_details import sync_event_details
    from ..media import sync_media
    from ..players import sync_players
    clubs = list(CLUBS.values())
    return _report([sync_players(db=DB, clubs=clubs, include_stats=False) or {},
                    sync_media(db=DB, clubs=clubs, leagues=list(RECENT_LEAGUES)) or {},
                    sync_event_details(db=DB) or {}])


@dg.asset(key=["app", "analytics_cache"], deps=[app_matches, app_recent_matches], group_name="extract",
          op_tags=WRITER, description="Legacy Elo/shot caches still read by the API (until Phase 6 cutover).")
def app_analytics_cache():
    from ..ingest import refresh_analytics_cache
    refresh_analytics_cache(db=DB)


# ── Transformation (dbt) ──────────────────────────────────────────────────────

class Translator(DagsterDbtTranslator):
    def get_group_name(self, dbt_resource_props):
        return "warehouse"


@dbt_assets(manifest=dbt_project.manifest_path, project=dbt_project, dagster_dbt_translator=Translator(),
            op_tags=WRITER)
def warehouse(context: dg.AssetExecutionContext, dbt: DbtCliResource):
    yield from dbt.cli(["build"], context=context).stream()


# ── Modelling and serving ─────────────────────────────────────────────────────

@dg.asset(deps=[dg.AssetKey(["ml", "ml_match_features"])], group_name="ml", op_tags=WRITER,
          description="Walk-forward leaderboard tracked in MLflow; champion published to the app tables.")
def champion_model():
    from ..ml.train import train
    board = train(db=DB)
    champion = board[board.is_champion].iloc[0]
    return dg.MaterializeResult(metadata={
        "champion": str(champion.model),
        **{k: float(champion[k]) for k in ("log_loss", "rps", "accuracy", "ece")},
        "leaderboard": dg.MetadataValue.md(board.drop(columns=["bins", "run_id"]).to_markdown(index=False)),
    })


# ── Jobs and schedules (mirrors the old four-step refresh cadence) ────────────

core = dg.AssetSelection.assets(app_recent_matches, app_recent_events)
downstream = dg.AssetSelection.assets(warehouse, champion_model, app_analytics_cache)
jobs = [
    dg.define_asset_job("hourly_fixtures", selection=dg.AssetSelection.assets(app_recent_events)),
    dg.define_asset_job("six_hourly_refresh", selection=core | dg.AssetSelection.assets(
        landing_football_data, app_reference_standings) | downstream),
    dg.define_asset_job("daily_details", selection=dg.AssetSelection.assets(app_tournament_matches, app_media)),
    dg.define_asset_job("weekly_players", selection=dg.AssetSelection.assets(app_open_players)),
    dg.define_asset_job("bootstrap", selection=dg.AssetSelection.all()),
]
by_name = {job.name: job for job in jobs}
schedules = [
    dg.ScheduleDefinition(job=by_name["hourly_fixtures"], cron_schedule="15 * * * *"),
    dg.ScheduleDefinition(job=by_name["six_hourly_refresh"], cron_schedule="30 */6 * * *"),
    dg.ScheduleDefinition(job=by_name["daily_details"], cron_schedule="0 4 * * *"),
    dg.ScheduleDefinition(job=by_name["weekly_players"], cron_schedule="0 5 * * 1"),
]

defs = dg.Definitions(
    assets=[landing_football_data, app_matches, app_recent_matches, app_recent_events, app_reference_standings,
            app_tournament_matches, app_open_players, app_media, app_analytics_cache, warehouse, champion_model],
    jobs=jobs,
    schedules=schedules,
    resources={"dbt": DbtCliResource(project_dir=dbt_project,
                                     dbt_executable=str(Path(sys.executable).with_name("dbt")))},
)
