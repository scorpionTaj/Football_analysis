"""Single-job data refresh orchestration for the local application."""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Callable, Iterable
from uuid import uuid4

from football_analysis.api.contracts import RefreshRequest, RefreshSourceOutcome, RefreshStatusResponse
from football_analysis.config import (
    CLUBS,
    OPENFOOTBALL_TOURNAMENTS,
    RECENT_LEAGUES,
    THESPORTSDB_LEAGUE_IDS,
    TOURNAMENTS,
    current_season,
)
from football_analysis.teams import team_key


Progress = Callable[[int, str, str], None]
@dataclass
class RefreshRunReport:
    outcomes: list[RefreshSourceOutcome] = field(default_factory=list)

    def add(self, step: int, source: str, result: dict | Iterable[dict] | None, *, required: bool = False) -> None:
        rows = [{"status": "success"}] if result is None else [result] if isinstance(result, dict) else result
        for row in rows:
            identity = next((str(row[key]) for key in ("league", "competition", "club", "name", "event_id") if key in row), None)
            if identity and "season" in row:
                identity = f"{identity}:{row['season']}"
            if identity and "event_kind" in row:
                identity = f"{identity}:{row['event_kind']}"
            self.outcomes.append(RefreshSourceOutcome(
                step=step, source=source, partition=identity,
                status=row.get("status", "success"), required=required,
                detail=row.get("detail"),
            ))

    def attempt(self, step: int, source: str, task: Callable[[], dict | Iterable[dict]], *, required: bool = False) -> dict | Iterable[dict] | None:
        try:
            result = task()
            self.add(step, source, result, required=required)
            return result
        except Exception as exc:
            self.add(step, source, {"status": "failed", "detail": str(exc)}, required=required)
            return None

    @property
    def failures(self) -> list[RefreshSourceOutcome]:
        return [row for row in self.outcomes if row.status in {"failed", "unavailable", "unsupported"}]

    @property
    def required_failures(self) -> list[RefreshSourceOutcome]:
        return [row for row in self.failures if row.required]

    @staticmethod
    def message(row: RefreshSourceOutcome) -> str:
        label = f"{row.source} ({row.partition})" if row.partition else row.source
        return f"{label}: {row.detail or row.status}"


RefreshRunner = Callable[[RefreshRequest, Progress], RefreshRunReport | None]


def _featured_clubs_in_scope(database: Path, competitions: set[str], season: int) -> list[str]:
    """Only enrich featured clubs taking part in a selected refresh scope."""
    if not competitions:
        return list(CLUBS.values())
    from football_analysis.ingest import connect

    codes = sorted(competitions)
    placeholders = ",".join("?" for _ in codes)
    with connect(database) as con:
        rows = con.execute(f"""
            SELECT home_team AS team FROM recent_matches
            WHERE league IN ({placeholders}) AND season=?
            UNION SELECT away_team FROM recent_matches
            WHERE league IN ({placeholders}) AND season=?
            UNION SELECT home_team FROM recent_events
            WHERE league IN ({placeholders}) AND season=?
            UNION SELECT away_team FROM recent_events
            WHERE league IN ({placeholders}) AND season=?
            UNION SELECT home_team FROM tournament_matches
            WHERE competition IN ({placeholders}) AND season=?
            UNION SELECT away_team FROM tournament_matches
            WHERE competition IN ({placeholders}) AND season=?
        """, [value for _ in range(6) for value in (*codes, season)]).fetchall()
    participants = {team_key(row[0]) for row in rows}
    return [
        value for label, value in CLUBS.items()
        if team_key(label) in participants or team_key(value) in participants
    ]


class RefreshCoordinator:
    """Run at most one refresh while exposing a small polling-safe status contract."""

    def __init__(self, status_path: Path | None = None):
        self._lock = threading.Lock()
        self._status_path = status_path
        self._state = RefreshStatusResponse()
        if status_path and status_path.exists():
            try:
                self._state = RefreshStatusResponse.model_validate_json(status_path.read_text())
            except (OSError, ValueError):
                self._state = RefreshStatusResponse(message="Previous refresh status could not be read.")
            if self._state.status == "running":
                self._state.status = "failed"
                self._state.error = "The application stopped before this refresh finished."
                self._state.message = "Earlier completed steps may have been applied; refresh again to resume."
                self._state.finished_at = datetime.now().replace(microsecond=0)
                self._save()

    def _save(self) -> None:
        if self._status_path is None:
            return
        self._status_path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self._status_path.with_name(f".{self._status_path.name}.{uuid4().hex}.tmp")
        try:
            temporary.write_text(self._state.model_dump_json())
            temporary.replace(self._status_path)
        finally:
            temporary.unlink(missing_ok=True)

    def status(self) -> RefreshStatusResponse:
        with self._lock:
            return self._state.model_copy(deep=True)

    def start(self, request: RefreshRequest, runner: RefreshRunner) -> RefreshStatusResponse:
        with self._lock:
            if self._state.status == "running":
                raise RuntimeError("A data refresh is already running")
            self._state = RefreshStatusResponse(
                job_id=str(uuid4()), status="running", current_step=0,
                target_step=request.target_step, completed_steps=[],
                step_name="Preparing", message="Closing the read snapshot safely.",
                started_at=datetime.now().replace(microsecond=0),
            )
            self._save()

        def progress(step: int, name: str, message: str) -> None:
            with self._lock:
                completed = list(self._state.completed_steps)
                if step > self._state.current_step and self._state.current_step > 0:
                    completed.append(self._state.current_step)
                self._state.current_step = step
                self._state.completed_steps = sorted(set(completed))
                self._state.step_name = name
                self._state.message = message
                self._save()

        def work() -> None:
            try:
                report = runner(request, progress) or RefreshRunReport()
                with self._lock:
                    completed = [*self._state.completed_steps, request.target_step]
                    failed_steps = {row.step for row in report.required_failures}
                    self._state.completed_steps = sorted(set(completed) - failed_steps)
                    self._state.current_step = request.target_step
                    self._state.source_outcomes = report.outcomes
                    self._state.failed_count = len(report.required_failures)
                    self._state.degraded_count = len(report.failures) - self._state.failed_count
                    self._state.source_messages = [report.message(row) for row in report.failures]
                    self._state.status = (
                        "failed" if self._state.failed_count else
                        "degraded" if self._state.degraded_count else "success"
                    )
                    self._state.step_name = "Needs retry" if self._state.failed_count else "Published"
                    if self._state.failed_count:
                        self._state.message = (
                            f"Refresh finished with {self._state.failed_count} required failure(s) and "
                            f"{self._state.degraded_count} degraded source(s). Successful stages remain applied."
                        )
                        self._state.error = report.message(report.required_failures[0])
                    elif self._state.degraded_count:
                        self._state.message = (
                            f"Refresh finished with {self._state.degraded_count} degraded source(s). "
                            "Successful stages remain applied."
                        )
                    else:
                        self._state.message = "The refreshed database is ready for the frontend."
                    self._state.finished_at = datetime.now().replace(microsecond=0)
                    self._save()
            except Exception as exc:
                with self._lock:
                    self._state.status = "failed"
                    self._state.error = str(exc)
                    self._state.failed_count = 1
                    self._state.source_messages = [str(exc)]
                    self._state.message = "Refresh stopped. Completed stages remain applied; the failed stage may be partial."
                    self._state.finished_at = datetime.now().replace(microsecond=0)
                    self._save()

        threading.Thread(target=work, name="football-data-refresh", daemon=True).start()
        return self.status()


def run_refresh_pipeline(database: Path, request: RefreshRequest, progress: Progress) -> RefreshRunReport:
    """Execute existing synchronizers up to the operator-selected depth."""
    season = request.season if request.season is not None else current_season()
    requested = set(request.competitions)
    domestic = [code for code in RECENT_LEAGUES if not requested or code in requested]
    tournaments = [code for code in TOURNAMENTS if code in requested]
    provider_tournaments = [
        code for code in TOURNAMENTS
        if code in THESPORTSDB_LEAGUE_IDS and (not requested or code in requested)
    ]
    report = RefreshRunReport()

    if request.target_step >= 1:
        progress(1, "Results and fixtures", "Downloading current results and the next listed fixtures.")
        if domestic:
            from football_analysis.recent import sync_recent
            from football_analysis.fixtures import sync_fixtures
            from football_analysis.open_fixtures import sync_open_fixtures
            try:
                recent_reports = sync_recent(
                    db=database, year=season, leagues=domestic,
                    refresh=request.force_download,
                )
                for row in recent_reports:
                    source = row.get("source", "Football-Data.co.uk")
                    report.add(1, source, row, required=source == "Football-Data.co.uk")
            except Exception as exc:
                report.add(1, "Football-Data.co.uk", {"status": "failed", "detail": str(exc)}, required=True)
            open_reports = report.attempt(1, "OpenFootball fixtures", lambda: sync_open_fixtures(
                db=database, season=season, leagues=domestic,
                refresh=request.force_download,
            )) or []
            fixture_report = report.attempt(1, "Weekly fixtures", lambda: sync_fixtures(
                db=database, season=season, leagues=domestic,
                refresh=request.force_download,
            )) or {"status": "failed"}
            full_schedules = sum(row["status"] in {"success", "cached"} for row in open_reports)
            weekly = fixture_report["status"] in {"success", "cached"}
            progress(
                1, "Results and fixtures",
                f"Results refreshed; {full_schedules} full league schedules available"
                f"; weekly fixture window {'available' if weekly else 'unavailable'}.",
            )
        if provider_tournaments:
            from football_analysis.recent import sync_cup_events
            report.attempt(1, "Cup events", lambda: sync_cup_events(
                db=database, season=season, competitions=provider_tournaments,
                refresh=request.force_download,
            ))

    if request.target_step >= 2:
        progress(2, "Tables and competitions", "Refreshing reference tables and selected tournaments.")
        supported = [code for code in domestic if code in {"E0", "D1", "I1", "F1", "SP1"}]
        if supported:
            from football_analysis.reference_standings import sync as sync_standings
            report.attempt(2, "Reference standings", lambda: sync_standings(
                db=database, years=[season], leagues=supported,
                refresh=request.force_download,
            ))
        openfootball_tournaments = [code for code in tournaments if code in OPENFOOTBALL_TOURNAMENTS]
        if openfootball_tournaments:
            from football_analysis.tournaments import OpenFootballTournaments, sync_tournaments
            report.attempt(2, "OpenFootball tournaments", lambda: sync_tournaments(
                db=database,
                partitions=[(code, season) for code in openfootball_tournaments],
                adapter=OpenFootballTournaments(refresh=request.force_download),
            ))

    if request.target_step >= 3:
        progress(3, "Teams, players and match detail", "Refreshing artwork, squads, formations and event detail.")
        from football_analysis.event_details import sync_event_details
        from football_analysis.media import sync_media
        from football_analysis.open_players import sync_open_players
        from football_analysis.players import sync_players

        report.attempt(3, "Open players", lambda: sync_open_players(
            db=database, refresh=request.force_download,
        ))
        try:
            featured = _featured_clubs_in_scope(database, requested, season)
        except Exception as exc:
            report.add(3, "Featured club scope", {"status": "failed", "detail": str(exc)})
            featured = []
        if featured:
            report.attempt(3, "Featured players", lambda: sync_players(
                db=database, clubs=featured, include_stats=False,
                refresh=request.force_download,
            ))
        media_leagues = [code for code in (*domestic, *tournaments) if code in THESPORTSDB_LEAGUE_IDS]
        report.attempt(3, "Media", lambda: sync_media(
            db=database, clubs=featured, leagues=media_leagues,
            refresh=request.force_download,
        ))
        report.attempt(3, "Event details", lambda: sync_event_details(
            db=database, refresh=request.force_download,
            leagues=[*domestic, *provider_tournaments] if requested else None,
        ))

    if request.target_step >= 4:
        progress(4, "Models and validation", "Rebuilding analytical caches and calibrated forecasts.")
        from football_analysis.ingest import refresh_analytics_cache
        from football_analysis.predictions import sync_predictions

        report.attempt(4, "Analytics cache", lambda: refresh_analytics_cache(db=database), required=True)
        report.attempt(4, "Predictions", lambda: sync_predictions(
            db=database, force=request.force_download,
        ), required=True)
    return report
