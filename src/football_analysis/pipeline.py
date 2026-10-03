"""One operator entry point for incremental refreshes and first-time backfills."""

from __future__ import annotations

import argparse
import json

import duckdb

from .api.contracts import RefreshRequest
from .api.refresh import RefreshRunReport, run_refresh_pipeline
from .config import CLUBS, DATA, DB, seasons


def run_pipeline(*, bootstrap=False, step=4, season=None, competitions=None,
                 force=False, all_media=False, max_teams=100, quick=False, db=DB):
    """Refresh published data; bootstrap adds the historical source backfill once."""
    report = RefreshRunReport()
    if bootstrap:
        from .adapters import FootballDataCSV
        from .ingest import ingest
        from .open_players import sync_open_players
        from .players import sync_players
        from .reference_standings import sync as sync_standings
        from .tournaments import OpenFootballTournaments, default_partitions, sync_tournaments

        tasks = (
            ("Historical league results", True, lambda: ingest(
                FootballDataCSV(DATA / "raw", refresh=force), db=db,
                years=seasons(),
            )),
            ("Historical standings", False, lambda: sync_standings(
                db=db, years=seasons(), refresh=force,
            )),
            ("Historical tournaments", False, lambda: sync_tournaments(
                db=db, partitions=default_partitions(),
                adapter=OpenFootballTournaments(refresh=force),
            )),
            ("Historical players and match context", False, lambda: sync_open_players(
                db=db, refresh=force,
            )),
            ("Featured player profiles and stats", False, lambda: sync_players(
                db=db, clubs=list(CLUBS.values()), include_stats=True, refresh=force,
            )),
        )
        for name, required, task in tasks:
            print(json.dumps({"stage": name, "status": "running"}), flush=True)
            report.attempt(0, name, task, required=required)

    request = RefreshRequest(
        target_step=4 if quick else step, season=season, competitions=competitions or [],
        force_download=force, quick=quick,
    )

    def progress(number, name, message):
        print(json.dumps({"step": number, "stage": name, "message": message}), flush=True)

    current = run_refresh_pipeline(db, request, progress)
    if current is not None:
        report.outcomes.extend(current.outcomes)
    if all_media:
        from .media import discover_missing_clubs, sync_media

        def backfill_media():
            clubs = discover_missing_clubs(db, retry_missing=force)[:max_teams]
            return sync_media(db=db, clubs=clubs, leagues=[], refresh=force, retry_missing=force)

        report.attempt(step, "Additional media", backfill_media)
    failed_count = len(report.required_failures)
    degraded_count = len(report.failures) - failed_count
    print(json.dumps({
        "status": "failed" if failed_count else "degraded" if degraded_count else "success",
        "bootstrap": bootstrap, "step": step,
        "failed_count": failed_count, "degraded_count": degraded_count,
        "source_messages": [report.message(row) for row in report.failures],
    }), flush=True)
    return report


def notify(title: str, message: str, priority: str = "high") -> bool:
    """Phone/desktop alert via ntfy (https://ntfy.sh). Silent no-op unless NTFY_TOPIC is set."""
    import os

    import requests

    topic = os.environ.get("NTFY_TOPIC")
    if not topic:
        return False
    try:
        requests.post(f"{os.environ.get('NTFY_SERVER', 'https://ntfy.sh')}/{topic}", data=message.encode(),
                      headers={"Title": title, "Priority": priority, "Tags": "soccer,warning"}, timeout=10)
        return True
    except requests.RequestException:
        return False  # an alert must never break the refresh itself


def main():
    parser = argparse.ArgumentParser(description="Refresh football data with one resumable command")
    parser.add_argument("--bootstrap", action="store_true", help="Include historical leagues, cups and player snapshots")
    parser.add_argument("--step", type=int, choices=range(1, 5), default=4, help="Refresh depth, 1-4 (default: 4)")
    parser.add_argument("--season", type=int, help="Current season start year")
    parser.add_argument("--competitions", nargs="+", help="Limit current refresh to competition codes")
    parser.add_argument("--force", action="store_true", help="Bypass source freshness checks and redownload")
    parser.add_argument("--quick", action="store_true",
                        help="Routine run: current results + fixtures, then warehouse, forecasts and publish")
    parser.add_argument("--all-media", action="store_true", help="Also backfill a bounded batch of missing badges")
    parser.add_argument("--max-teams", type=int, default=100, help="Maximum badge lookups with --all-media")
    args = parser.parse_args()
    if args.max_teams < 1:
        parser.error("--max-teams must be positive")
    try:
        report = run_pipeline(
            bootstrap=args.bootstrap, step=args.step, season=args.season,
            competitions=args.competitions, force=args.force,
            all_media=args.all_media, max_teams=args.max_teams, quick=args.quick,
        )
        if report.required_failures:
            notify("Football refresh failed",
                   "\n".join(report.message(row) for row in report.required_failures)[:3500])
            raise SystemExit(1)
    except duckdb.ConnectionException as exc:
        if "different configuration" not in str(exc) and "being used" not in str(exc):
            notify("Football refresh crashed", f"{type(exc).__name__}: {exc}"[:3500])
            raise
        notify("Football refresh skipped", "DuckDB is open in another process (football-api on DuckDB?).", "default")
        parser.exit(2, "Database is already open for API reads. Stop football-api, "
                       "or refresh through Settings instead.\n")
    except Exception as exc:
        notify("Football refresh crashed", f"{type(exc).__name__}: {exc}"[:3500])
        raise


if __name__ == "__main__":
    main()
