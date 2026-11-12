"""FastAPI application with read views and one explicit local refresh workflow."""

from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import os
import time
from contextlib import asynccontextmanager
from datetime import date
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse, RedirectResponse

from football_analysis.api import queries
from football_analysis.api.contracts import (
    AnalysisReportResponse,
    AnalysisRequestBody,
    CatalogResponse,
    EventDetailResponse,
    EventListResponse,
    HealthResponse,
    MatchListResponse,
    MatchCentreDetailResponse,
    OverviewResponse,
    PlayerListResponse,
    PlayerProfileResponse,
    ModelsResponse,
    PipelineResponse,
    PredictionsResponse,
    QualityResponse,
    RefreshRequest,
    RefreshStatusResponse,
    ShotAnalysisResponse,
    StandingsResponse,
    TeamListResponse,
    TournamentResponse,
    TransferListResponse,
)
from football_analysis.api.db import PostgresReadOnlyStore, ReadOnlyStore, SQLiteReadOnlyStore
from football_analysis.api.refresh import RefreshCoordinator, RefreshRunner, run_refresh_pipeline
from football_analysis.api.response_cache import RedisResponseCache
from football_analysis.config import DB, LOCAL_SNAPSHOT, TOURNAMENTS, current_season


CACHE_SHORT = "public, max-age=60, stale-while-revalidate=300"
CACHE_STABLE = "public, max-age=300, stale-while-revalidate=3600"
CACHE_HISTORICAL = "public, max-age=86400, stale-while-revalidate=604800"
CACHE_DETAIL = "public, max-age=0, must-revalidate"
CACHE_REVISION = "catalog-overview-v1"


def cache_for_season(season: int | None) -> str:
    return CACHE_HISTORICAL if season is not None and season < current_season() else CACHE_SHORT


def create_app(
    database_path: Path | None = None,
    refresh_runner: RefreshRunner | None = None,
    defer_database_open: bool = False,
    response_cache: RedisResponseCache | None = None,
) -> FastAPI:
    path = Path(database_path) if database_path is not None else DB
    read_backend = os.environ.get("FOOTBALL_API_READ_BACKEND", "duckdb").lower()
    if read_backend not in {"duckdb", "postgres"}:
        raise ValueError("FOOTBALL_API_READ_BACKEND must be duckdb or postgres")
    postgres_dsn = os.environ.get("FOOTBALL_POSTGRES_DSN")
    local_snapshot = LOCAL_SNAPSHOT if database_path is None else path.with_suffix(".sqlite3")

    def open_store() -> ReadOnlyStore | PostgresReadOnlyStore | SQLiteReadOnlyStore:
        if read_backend == "postgres":
            if postgres_dsn:
                from psycopg import OperationalError

                try:
                    return PostgresReadOnlyStore(
                        postgres_dsn, os.environ.get("FOOTBALL_POSTGRES_SCHEMA", "football_analysis_next"),
                    )
                except (OperationalError, ValueError):  # unreachable, or schema not published yet
                    pass
            return SQLiteReadOnlyStore(local_snapshot)
        return ReadOnlyStore(path)

    store: ReadOnlyStore | PostgresReadOnlyStore | SQLiteReadOnlyStore | None
    if defer_database_open:
        store = None
    else:
        try:
            store = open_store()
        except FileNotFoundError:
            store = None

    @asynccontextmanager
    async def lifespan(application: FastAPI):
        if defer_database_open and application.state.store is None and (read_backend == "postgres" or path.exists()):
            try:
                application.state.store = open_store()
            except FileNotFoundError:
                pass
        try:
            yield
        finally:
            current = application.state.store
            if current is not None:
                current.close()
                application.state.store = None

    app = FastAPI(
        title="Football Analysis API",
        version="1.0.0",
        openapi_url="/openapi.json",
        docs_url="/",  # the API's home page is its interactive documentation (Swagger UI)
        lifespan=lifespan,
    )

    @app.get("/docs", include_in_schema=False)
    def docs_redirect():
        """The docs moved to `/`; keep the conventional path working."""
        return RedirectResponse("/")
    app.add_middleware(GZipMiddleware, minimum_size=1024)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:3000",
            "http://127.0.0.1:3000",
            "http://localhost:3001",
            "http://127.0.0.1:3001",
            # Deployed web origins, comma-separated (the browser calls the API directly).
            *(origin.strip() for origin in os.environ.get("FOOTBALL_CORS_ORIGINS", "").split(",") if origin.strip()),
        ],
        allow_origin_regex=r"^https?://(localhost|127\.0\.0\.1)(:[0-9]+)?$",
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["*"],
        expose_headers=["ETag", "Cache-Control"],
    )
    app.state.store = store
    app.state.fallback_since = time.monotonic()
    app.state.database_path = path
    app.state.refresh = RefreshCoordinator(path.with_suffix(".refresh.json"))
    response_cache = response_cache if response_cache is not None else RedisResponseCache.from_environment()

    def require_store() -> ReadOnlyStore | PostgresReadOnlyStore | SQLiteReadOnlyStore:
        current = app.state.store
        if current is None:
            raise HTTPException(status_code=503, detail="Database is unavailable")
        # Serving the SQLite fallback in postgres mode: retry PostgreSQL every five minutes.
        if (read_backend == "postgres" and postgres_dsn and isinstance(current, SQLiteReadOnlyStore)
                and time.monotonic() - app.state.fallback_since >= 300):
            replace_store()
            current = app.state.store
        return current

    def replace_store() -> None:
        app.state.fallback_since = time.monotonic()
        try:
            fresh = open_store()
        except (FileNotFoundError, ValueError):
            return
        old, app.state.store = app.state.store, fresh
        if old is not None:
            old.close()

    if read_backend == "postgres" and postgres_dsn:
        from psycopg import Error as PostgresError

        @app.exception_handler(PostgresError)
        async def postgres_unavailable(_request: Request, _exc: PostgresError):
            # The store already reconnected once; switch to whatever open_store() can reach.
            replace_store()
            return JSONResponse({"detail": "Database connection lost; retry"}, status_code=503)

    def authorize_refresh(request: Request) -> None:
        """Refresh runs downloads and rewrites data: loopback callers, or a matching admin token."""
        token = os.environ.get("FOOTBALL_ADMIN_TOKEN")
        supplied = request.headers.get("x-admin-token")
        if token and supplied and hmac.compare_digest(token.encode(), supplied.encode()):
            return
        if not token and request.client and request.client.host in {"127.0.0.1", "::1"}:
            return
        raise HTTPException(status_code=403, detail="Refresh requires FOOTBALL_ADMIN_TOKEN (X-Admin-Token header)")

    def with_cache(payload, request: Request, cache: str = CACHE_SHORT, etag: str | None = None) -> Response:
        body = payload.model_dump(mode="json")
        etag = etag or (queries.snapshot_etag(require_store()) if app.state.store else '"empty"')
        if request.headers.get("if-none-match") == etag:
            return Response(status_code=304, headers={"ETag": etag, "Cache-Control": cache})
        return JSONResponse(body, headers={"ETag": etag, "Cache-Control": cache})

    def with_redis_cache(request: Request, build, cache_control: str, ttl: int) -> Response:
        store = require_store()
        # Include every query pair, including duplicates and unknown parameters.
        # Sort names but retain the order of repeated values: FastAPI may use
        # the last value for a repeated parameter.
        identity = json.dumps(
            [queries.API_SCHEMA_REVISION, CACHE_REVISION, store.generation,
             date.today().isoformat(), request.url.path,
             sorted(request.query_params.multi_items(), key=lambda pair: pair[0])],
            separators=(",", ":"),
        )
        digest = hashlib.sha256(identity.encode()).hexdigest()
        key = f"football-api:{digest}"
        etag = f'"{digest}"'
        headers = {"ETag": etag, "Cache-Control": cache_control}
        if request.headers.get("if-none-match") == etag:
            return Response(status_code=304, headers=headers)
        cached = response_cache.get(key) if response_cache is not None else None
        if cached is not None:
            return Response(content=cached, media_type="application/json", headers=headers)
        body = JSONResponse(build(store).model_dump(mode="json"), headers=headers)
        if response_cache is not None:
            response_cache.set(key, body.body, ttl)
        return body

    @app.get("/api/v1/health", response_model=HealthResponse)
    def health():
        return queries.health(app.state.store)

    @app.get("/api/v1/catalog", response_model=CatalogResponse)
    def catalog(request: Request):
        return with_redis_cache(request, queries.catalog, CACHE_STABLE, 300)

    @app.get("/api/v1/teams", response_model=TeamListResponse)
    def teams(
        request: Request,
        competition: str | None = None,
        season: int | None = None,
    ):
        return with_cache(queries.list_teams(require_store(), competition, season), request, cache_for_season(season))

    @app.get("/api/v1/matches", response_model=MatchListResponse)
    def matches(
        request: Request,
        competition: str | None = None,
        season: int | None = None,
        team: str | None = None,
        opponent: str | None = None,
        venue: str | None = None,
        q: str | None = None,
        cursor: str | None = None,
        limit: int = Query(default=50, ge=1, le=200),
    ):
        try:
            payload = queries.list_matches(
                require_store(), competition, season, team, opponent, venue, cursor, limit, q,
                source_name="postgresql" if isinstance(app.state.store, PostgresReadOnlyStore)
                else "sqlite" if isinstance(app.state.store, SQLiteReadOnlyStore) else "duckdb",
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return with_cache(payload, request, cache_for_season(season))

    @app.get("/api/v1/shots", response_model=ShotAnalysisResponse)
    def shots(
        request: Request,
        competition: str | None = None,
        season: int | None = None,
        team: str | None = None,
    ):
        return with_cache(queries.shot_analysis(require_store(), competition, season, team), request, cache_for_season(season))

    @app.get("/api/v1/event-details", response_model=EventListResponse)
    def event_details(
        request: Request,
        competition: str | None = None,
        season: int | None = None,
    ):
        return with_cache(queries.list_event_details(require_store(), competition, season), request, cache_for_season(season))

    @app.get("/api/v1/event-details/{event_id}", response_model=EventDetailResponse)
    def event_detail(event_id: str, request: Request):
        payload = queries.event_detail(require_store(), event_id)
        if payload is None:
            raise HTTPException(status_code=404, detail="Event details not found")
        return with_cache(payload, request, CACHE_STABLE)

    @app.get("/api/v1/match-detail", response_model=MatchCentreDetailResponse)
    def match_detail(
        request: Request,
        competition: str,
        season: int,
        match_date: str,
        home: str,
        away: str,
    ):
        payload = queries.match_centre_detail(
            require_store(), competition, season, match_date, home, away,
        )
        if payload is None:
            raise HTTPException(status_code=404, detail="Match not found")
        return with_cache(payload, request, CACHE_DETAIL)

    @app.post("/api/v1/analysis", response_model=AnalysisReportResponse)
    def analysis(body: AnalysisRequestBody, request: Request):
        if body.form_window < 1:
            raise HTTPException(status_code=400, detail="form_window must be positive")
        payload = queries.build_analysis(require_store(), body)
        return with_cache(payload, request, "private, max-age=10")

    @app.get("/api/v1/tournaments/{competition}/{season}", response_model=TournamentResponse)
    def tournament(competition: str, season: int, request: Request):
        if competition not in TOURNAMENTS:
            raise HTTPException(status_code=404, detail="Unknown tournament")
        return with_cache(queries.tournament(require_store(), competition, season), request, cache_for_season(season))

    @app.get("/api/v1/predictions", response_model=PredictionsResponse)
    def predictions(request: Request):
        return with_cache(queries.predictions(require_store()), request, CACHE_STABLE)

    @app.get("/api/v1/models", response_model=ModelsResponse)
    def models(request: Request):
        return with_cache(queries.models(require_store()), request, CACHE_STABLE)

    @app.get("/api/v1/pipeline", response_model=PipelineResponse)
    def pipeline(request: Request):
        return with_cache(queries.pipeline(require_store()), request, CACHE_STABLE)

    @app.get("/api/v1/players", response_model=PlayerListResponse)
    def players(
        request: Request,
        q: str | None = None,
        team: str | None = None,
        position: str | None = None,
        sort_by: str | None = None,
        cursor: str | None = None,
        limit: int = Query(default=50, ge=1, le=200),
    ):
        try:
            payload = queries.list_players(require_store(), q, team, position, sort_by, cursor, limit)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return with_cache(payload, request)

    @app.get("/api/v1/players/{player_id}", response_model=PlayerProfileResponse)
    def player(player_id: str, request: Request):
        payload = queries.get_player(require_store(), player_id)
        if payload is None:
            raise HTTPException(status_code=404, detail="Player not found")
        return with_cache(payload, request, CACHE_STABLE)

    @app.get("/api/v1/quality", response_model=QualityResponse)
    def quality(request: Request):
        return with_cache(queries.quality(require_store()), request, CACHE_STABLE)

    @app.get("/api/v1/standings", response_model=StandingsResponse)
    def standings(
        request: Request,
        competition: str,
        season: int,
        form_window: int = Query(default=5, ge=1, le=10),
        venue: str | None = None,
    ):
        return with_cache(
            queries.standings(require_store(), competition, season, form_window, venue),
            request,
            cache_for_season(season),
        )

    @app.get("/api/v1/overview", response_model=OverviewResponse)
    def overview(
        request: Request,
        team: str | None = None,
        competition: str | None = None,
        season: int | None = None,
    ):
        return with_redis_cache(
            request,
            lambda store: queries.overview(store, team, competition, season),
            CACHE_SHORT,
            60,
        )

    @app.get("/api/v1/transfers", response_model=TransferListResponse)
    def transfers(
        request: Request,
        season: str | None = None,
        competition: str | None = None,
        club: str | None = None,
        q: str | None = None,
        cursor: str | None = None,
        limit: int = Query(default=50, ge=1, le=200),
    ):
        season_val: int | None = None
        if season is not None and str(season).lower() not in ("all", "any", "none", ""):
            try:
                season_val = int(season)
            except ValueError:
                season_val = None
        try:
            payload = queries.list_transfers(
                require_store(),
                season=season_val,
                competition=competition,
                club=club,
                query=q,
                cursor=cursor,
                limit=limit,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return with_cache(payload, request)

    @app.get("/api/v1/refresh", response_model=RefreshStatusResponse)
    def refresh_status():
        return app.state.refresh.status()

    @app.post("/api/v1/refresh", response_model=RefreshStatusResponse, status_code=202)
    def start_refresh(body: RefreshRequest, request: Request):
        authorize_refresh(request)

        def execute(refresh_request: RefreshRequest, progress):
            # Only a DuckDB read store conflicts with the writer; PostgreSQL/SQLite keep serving.
            if read_backend == "duckdb" and app.state.store is not None:
                app.state.store.close()
                app.state.store = None
            try:
                runner = refresh_runner or (
                    lambda req, update: run_refresh_pipeline(path, req, update)
                )
                return runner(refresh_request, progress)
            finally:
                if app.state.store is None:
                    app.state.store = open_store()
                else:
                    replace_store()

        try:
            return app.state.refresh.start(body, execute)
        except RuntimeError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    return app


app = create_app(defer_database_open=True)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the read-only football analysis API")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    import uvicorn
    uvicorn.run("football_analysis.api.app:app", host=args.host, port=args.port, reload=False)


if __name__ == "__main__":
    main()
