"""Snapshot identity, health, and the catalog of competitions and teams."""

from __future__ import annotations

import hashlib

import pandas as pd

from football_analysis.api.contracts import (
    CatalogResponse,
    Competition,
    HealthResponse,
    SeasonCoverage,
    Team,
    TeamListResponse,
    canonical_team_id,
)
from football_analysis.api.db import ReadOnlyStore
from football_analysis.config import (
    CALENDAR_YEAR_TOURNAMENTS,
    COMPETITION_GROUPS,
    COMPETITION_REGIONS,
    COMPETITIONS,
    TOURNAMENTS,
    current_season,
    label,
    seasons,
)
from football_analysis.teams import display_team
from football_analysis.api.queries._shared import (
    _as_date,
    _competition_media_map,
    _has,
    _source,
    _store_source,
    _team_media_map,
)


API_SCHEMA_REVISION = "2026-09-23-full-fixtures-season-form-v1"


def snapshot_etag(store: ReadOnlyStore) -> str:
    # The former count/max(timestamp) list missed reference_standings,
    # team_media, competition_media, recent_events, and several prediction and
    # analytics tables. It also missed in-place edits at an unchanged stamp.
    # A read-only store is replaced after refresh, so its generation covers
    # the entire published snapshot without touching DuckDB per request.
    digest = hashlib.md5(
        f"{API_SCHEMA_REVISION}|{store.generation}".encode(), usedforsecurity=False
    ).hexdigest()
    return f'"{digest}"'


def health(store: ReadOnlyStore | None) -> HealthResponse:
    if store is None:
        return HealthResponse(status="unavailable", database="missing", read_only=True)
    return HealthResponse(status="ok", database=str(store.path), read_only=True)


def catalog(store: ReadOnlyStore) -> CatalogResponse:
    live = current_season()
    completed = set(seasons())
    media_map = _competition_media_map(store)
    rows = []
    if _has(store, "mart_dashboard_match"):
        rows.append(store.query(
            "SELECT league AS competition, season, count(*) AS match_count, max(match_date) AS latest_match "
            "FROM mart_dashboard_match GROUP BY 1, 2"
        ))
    if _has(store, "recent_matches"):
        rows.append(store.query(
            "SELECT league AS competition, season, count(*) AS match_count, max(match_date) AS latest_match "
            "FROM recent_matches GROUP BY 1, 2"
        ))
    if _has(store, "fct_tournament_match"):
        rows.append(store.query(
            "SELECT competition, season, count(*) AS match_count, max(match_date) AS latest_match "
            "FROM fct_tournament_match GROUP BY 1, 2"
        ))
    coverage = pd.concat(rows, ignore_index=True) if rows else pd.DataFrame(
        columns=["competition", "season", "match_count", "latest_match"]
    )
    if not coverage.empty:
        coverage = coverage.groupby(["competition", "season"], as_index=False).agg(
            match_count=("match_count", "sum"), latest_match=("latest_match", "max"),
        )
    freshness = None
    if _has(store, "ingestion_runs"):
        freshness = store.scalar("SELECT max(fetched_at) FROM ingestion_runs")
    competitions: list[Competition] = []
    for code, name in COMPETITIONS.items():
        kind = "tournament" if code in TOURNAMENTS else "domestic"
        subset = coverage[coverage.competition == code] if not coverage.empty else coverage
        season_rows: list[SeasonCoverage] = []
        years = sorted(set(int(year) for year in subset.season.tolist())) if not subset.empty else []
        for year in years:
            row = subset[subset.season == year].iloc[0]
            if year == live:
                status = "live_partial"
            elif year in completed:
                status = "complete"
            else:
                status = "complete"
            season_rows.append(SeasonCoverage(
                season=int(year),
                label=str(year) if code in CALENDAR_YEAR_TOURNAMENTS else label(int(year)),
                match_count=int(row.match_count),
                latest_match=_as_date(row.latest_match),
                status=status,
            ))
        media = media_map.get(code)
        competitions.append(Competition(
            code=code, name=name, kind=kind,
            group=COMPETITION_GROUPS.get(code, "Other competitions"),
            region=COMPETITION_REGIONS.get(code), seasons=season_rows,
            source=_source(
                "football-data.co.uk" if kind == "domestic" else "OpenFootball + Transfermarkt Open Dataset",
                "loaded partitions only", freshness,
            ),
            badge_url=getattr(media, "badge_url", None) or None,
            logo_url=getattr(media, "logo_url", None) or None,
            banner_url=getattr(media, "banner_url", None) or None,
            trophy_url=getattr(media, "trophy_url", None) or None,
            fanart_url=getattr(media, "fanart_url", None) or None,
        ))
    return CatalogResponse(
        competitions=competitions,
        current_season=live,
        generated_at=store.opened_at,
        source=_source(_store_source(store), "catalog", freshness),
    )


def list_teams(store: ReadOnlyStore, competition: str | None, season: int | None) -> TeamListResponse:
    if not (_has(store, "mart_dashboard_team_season") or _has(store, "recent_matches") or _has(store, "fct_tournament_match")):
        return TeamListResponse(teams=[], source=_source(_store_source(store), "empty"))

    # Unified query combining historical team_seasons, live recent_matches, and tournament_matches
    q = """
    WITH all_season_teams AS (
        -- Historical team_seasons
        SELECT league, season, team, played, points FROM mart_dashboard_team_season
        UNION ALL
        -- Recent matches (both completed and scheduled)
        SELECT
            m.league,
            m.season,
            m.team,
            count(CASE WHEN m.home_goals IS NOT NULL OR m.away_goals IS NOT NULL THEN 1 END) AS played,
            sum(COALESCE(m.points, 0)) AS points
        FROM (
            SELECT league, season, home_team AS team, home_goals, away_goals,
                   CASE WHEN home_goals > away_goals THEN 3 WHEN home_goals = away_goals THEN 1 ELSE 0 END AS points
            FROM recent_matches
            UNION ALL
            SELECT league, season, away_team AS team, home_goals, away_goals,
                   CASE WHEN away_goals > home_goals THEN 3 WHEN away_goals = home_goals THEN 1 ELSE 0 END AS points
            FROM recent_matches
        ) m
        WHERE NOT EXISTS (SELECT 1 FROM mart_dashboard_team_season ts WHERE ts.league = m.league AND ts.season = m.season)
        GROUP BY m.league, m.season, m.team
        UNION ALL
        -- Tournament matches
        SELECT
            t.competition AS league,
            t.season,
            t.team,
            count(CASE WHEN t.home_goals IS NOT NULL OR t.away_goals IS NOT NULL THEN 1 END) AS played,
            sum(COALESCE(t.points, 0)) AS points
        FROM (
            SELECT competition, season, home_team AS team, home_goals, away_goals,
                   CASE WHEN home_goals > away_goals THEN 3 WHEN home_goals = away_goals THEN 1 ELSE 0 END AS points
            FROM fct_tournament_match
            UNION ALL
            SELECT competition, season, away_team AS team, home_goals, away_goals,
                   CASE WHEN away_goals > home_goals THEN 3 WHEN away_goals = home_goals THEN 1 ELSE 0 END AS points
            FROM fct_tournament_match
        ) t
        WHERE NOT EXISTS (SELECT 1 FROM mart_dashboard_team_season ts WHERE ts.league = t.competition AND ts.season = t.season)
        GROUP BY t.competition, t.season, t.team
    )
    SELECT league, season, team, played, points FROM all_season_teams WHERE 1=1
    """
    params: list = []
    if competition:
        q += " AND league = ?"
        params.append(competition)
    if season is not None:
        q += " AND season = ?"
        params.append(season)
    q += " ORDER BY league, season, team"

    try:
        frame = store.query(q, params)
    except Exception:
        frame = pd.DataFrame(columns=["league", "season", "team", "played", "points"])

    # Fallback: if a specific season has no teams for the competition, return all known teams for that competition
    if frame.empty and competition:
        fallback_q = """
        SELECT DISTINCT league, ? AS season, team, 0 AS played, 0 AS points
        FROM (
            SELECT league, team FROM mart_dashboard_team_season WHERE league = ?
            UNION
            SELECT league, home_team AS team FROM recent_matches WHERE league = ?
            UNION
            SELECT league, away_team AS team FROM recent_matches WHERE league = ?
            UNION
            SELECT competition AS league, home_team AS team FROM fct_tournament_match WHERE competition = ?
            UNION
            SELECT competition AS league, away_team AS team FROM fct_tournament_match WHERE competition = ?
        )
        ORDER BY team
        """
        fallback_season = season if season is not None else 2026
        try:
            frame = store.query(fallback_q, [fallback_season, competition, competition, competition, competition, competition])
        except Exception:
            pass

    tm_map = _team_media_map(store)
    teams = [
        Team(
            team_id=canonical_team_id(row.team),
            name=display_team(row.team) or row.team,
            competition=row.league,
            season=int(row.season),
            played=int(row.played or 0),
            points=int(row.points or 0),
            badge_url=getattr(tm_map.get(canonical_team_id(row.team)), "badge_url", None) or None,
            logo_url=getattr(tm_map.get(canonical_team_id(row.team)), "logo_url", None) or None,
        )
        for row in frame.itertuples(index=False)
    ]
    return TeamListResponse(teams=teams, source=_source(_store_source(store), "teams"))
