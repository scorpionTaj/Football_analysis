"""Read-only FastAPI application. Synchronizers stay outside request handlers."""

from __future__ import annotations

import argparse
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from football_analysis.api import queries
from football_analysis.api.contracts import AnalysisRequestBody, HealthResponse
from football_analysis.api.db import ReadOnlyStore
from football_analysis.config import DB, TOURNAMENTS


CACHE_SHORT = "public, max-age=15"
CACHE_STABLE = "public, max-age=60"


def create_app(database_path: Path | None = None) -> FastAPI:
    path = Path(database_path) if database_path is not None else DB
    store: ReadOnlyStore | None
    try:
        store = ReadOnlyStore(path)
    except FileNotFoundError:
        store = None

    app = FastAPI(
        title="Football Analysis API",
        version="1.0.0",
        openapi_url="/openapi.json",
        docs_url="/docs",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:3000",
            "http://127.0.0.1:3000",
            "http://localhost:3001",
            "http://127.0.0.1:3001",
        ],
        allow_origin_regex=r"^https?://(localhost|127\.0\.0\.1)(:[0-9]+)?$",
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["*"],
        expose_headers=["ETag", "Cache-Control"],
    )
    app.state.store = store
    app.state.database_path = path

    def require_store() -> ReadOnlyStore:
        current = app.state.store
        if current is None:
            raise HTTPException(status_code=503, detail="Database is unavailable")
        return current

    def with_cache(payload, request: Request, cache: str = CACHE_SHORT) -> Response:
        body = payload.model_dump(mode="json")
        etag = queries.snapshot_etag(require_store()) if app.state.store else '"empty"'
        if request.headers.get("if-none-match") == etag:
            return Response(status_code=304, headers={"ETag": etag, "Cache-Control": cache})
        return JSONResponse(body, headers={"ETag": etag, "Cache-Control": cache})

    @app.get("/api/v1/health", response_model=HealthResponse)
    def health():
        return queries.health(app.state.store)

    @app.get("/api/v1/catalog")
    def catalog(request: Request):
        return with_cache(queries.catalog(require_store()), request, CACHE_STABLE)

    @app.get("/api/v1/teams")
    def teams(
        request: Request,
        competition: str | None = None,
        season: int | None = None,
    ):
        return with_cache(queries.list_teams(require_store(), competition, season), request)

    @app.get("/api/v1/matches")
    def matches(
        request: Request,
        competition: str | None = None,
        season: int | None = None,
        team: str | None = None,
        venue: str | None = None,
        cursor: str | None = None,
        limit: int = Query(default=50, ge=1, le=200),
    ):
        try:
            payload = queries.list_matches(
                require_store(), competition, season, team, venue, cursor, limit,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return with_cache(payload, request)

    @app.post("/api/v1/analysis")
    def analysis(body: AnalysisRequestBody, request: Request):
        if body.form_window < 1:
            raise HTTPException(status_code=400, detail="form_window must be positive")
        payload = queries.build_analysis(require_store(), body)
        return with_cache(payload, request, "private, max-age=10")

    @app.get("/api/v1/tournaments/{competition}/{season}")
    def tournament(competition: str, season: int, request: Request):
        if competition not in TOURNAMENTS:
            raise HTTPException(status_code=404, detail="Unknown tournament")
        return with_cache(queries.tournament(require_store(), competition, season), request, CACHE_STABLE)

    @app.get("/api/v1/predictions")
    def predictions(request: Request):
        return with_cache(queries.predictions(require_store()), request, CACHE_STABLE)

    @app.get("/api/v1/players")
    def players(
        request: Request,
        q: str | None = None,
        team: str | None = None,
        sort_by: str | None = None,
        cursor: str | None = None,
        limit: int = Query(default=50, ge=1, le=200),
    ):
        try:
            payload = queries.list_players(require_store(), q, team, sort_by, cursor, limit)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return with_cache(payload, request)

    @app.get("/api/v1/players/{player_id}")
    def player(player_id: str, request: Request):
        payload = queries.get_player(require_store(), player_id)
        if payload is None:
            raise HTTPException(status_code=404, detail="Player not found")
        return with_cache(payload, request, CACHE_STABLE)

    @app.get("/api/v1/quality")
    def quality(request: Request):
        return with_cache(queries.quality(require_store()), request, CACHE_STABLE)

    @app.get("/api/v1/overview")
    def overview(
        request: Request,
        team: str | None = None,
        competition: str | None = None,
        season: int | None = None,
    ):
        return with_cache(queries.overview(require_store(), team, competition, season), request)

    return app


app = create_app()


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the read-only football analysis API")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    import uvicorn
    uvicorn.run("football_analysis.api.app:app", host=args.host, port=args.port, reload=False)


if __name__ == "__main__":
    main()
