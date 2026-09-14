"""Single-job data refresh orchestration for the local application."""

from __future__ import annotations

import threading
from datetime import datetime
from pathlib import Path
from typing import Callable
from uuid import uuid4

from football_analysis.api.contracts import RefreshRequest, RefreshStatusResponse
from football_analysis.config import (
    CLUBS,
    RECENT_LEAGUES,
    THESPORTSDB_LEAGUE_IDS,
    TOURNAMENTS,
    current_season,
)


Progress = Callable[[int, str, str], None]
RefreshRunner = Callable[[RefreshRequest, Progress], None]


class RefreshCoordinator:
    """Run at most one refresh while exposing a small polling-safe status contract."""

    def __init__(self):
        self._lock = threading.Lock()
        self._state = RefreshStatusResponse()

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

        def progress(step: int, name: str, message: str) -> None:
            with self._lock:
                completed = list(self._state.completed_steps)
                if step > self._state.current_step and self._state.current_step > 0:
                    completed.append(self._state.current_step)
                self._state.current_step = step
                self._state.completed_steps = sorted(set(completed))
                self._state.step_name = name
                self._state.message = message

        def work() -> None:
            try:
                runner(request, progress)
                with self._lock:
                    completed = [*self._state.completed_steps, request.target_step]
                    self._state.completed_steps = sorted(set(completed))
                    self._state.current_step = request.target_step
                    self._state.status = "success"
                    self._state.step_name = "Published"
                    self._state.message = "The refreshed database is ready for the frontend."
                    self._state.finished_at = datetime.now().replace(microsecond=0)
            except Exception as exc:
                with self._lock:
                    self._state.status = "failed"
                    self._state.error = str(exc)
                    self._state.message = "Refresh stopped; the previous valid data remains available."
                    self._state.finished_at = datetime.now().replace(microsecond=0)

        threading.Thread(target=work, name="football-data-refresh", daemon=True).start()
        return self.status()


def run_refresh_pipeline(database: Path, request: RefreshRequest, progress: Progress) -> None:
    """Execute existing synchronizers up to the operator-selected depth."""
    season = request.season if request.season is not None else current_season()
    requested = set(request.competitions)
    domestic = [code for code in RECENT_LEAGUES if not requested or code in requested]
    tournaments = [code for code in TOURNAMENTS if code in requested]

    if request.target_step >= 1:
        progress(1, "Results and fixtures", "Downloading current results and the next listed fixtures.")
        if domestic:
            from football_analysis.recent import sync_recent
            report = sync_recent(
                db=database, year=season, leagues=domestic,
                refresh=request.force_download,
            )
            if report and all(row.get("status") == "failed" for row in report):
                raise RuntimeError("No result partition could be refreshed")

    if request.target_step >= 2:
        progress(2, "Tables and competitions", "Refreshing reference tables and selected tournaments.")
        supported = [code for code in domestic if code in {"E0", "D1", "I1", "F1", "SP1"}]
        if supported:
            from football_analysis.reference_standings import sync as sync_standings
            sync_standings(db=database, years=[season], leagues=supported)
        if tournaments:
            from football_analysis.tournaments import OpenFootballTournaments, sync_tournaments
            sync_tournaments(
                db=database,
                partitions=[(code, season) for code in tournaments],
                adapter=OpenFootballTournaments(refresh=request.force_download),
            )

    if request.target_step >= 3:
        progress(3, "Teams, players and match detail", "Refreshing artwork, squads, formations and event detail.")
        from football_analysis.event_details import sync_event_details
        from football_analysis.media import sync_media
        from football_analysis.open_players import sync_open_players
        from football_analysis.players import sync_players

        sync_open_players(db=database, refresh=request.force_download)
        sync_players(db=database, clubs=list(CLUBS.values()), include_stats=False)
        media_leagues = [code for code in (*domestic, *tournaments) if code in THESPORTSDB_LEAGUE_IDS]
        sync_media(db=database, clubs=list(CLUBS.values()), leagues=media_leagues)
        sync_event_details(db=database)

    if request.target_step >= 4:
        progress(4, "Models and validation", "Rebuilding analytical caches and calibrated forecasts.")
        from football_analysis.ingest import refresh_analytics_cache
        from football_analysis.predictions import sync_predictions

        refresh_analytics_cache(db=database)
        sync_predictions(db=database)
