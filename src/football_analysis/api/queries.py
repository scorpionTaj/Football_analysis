"""DuckDB reads that power the versioned API."""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from datetime import date, datetime
from difflib import SequenceMatcher

import numpy as np
import pandas as pd

from football_analysis.analysis_system import (
    AnalysisRequest,
    AnalysisSystem,
    team_match_factors,
    tournament_team_matches,
)
from football_analysis.api.contracts import (
    AnalysisFilters,
    AnalysisReportResponse,
    CalibrationBin,
    CatalogResponse,
    ClubSpotlight,
    Competition,
    CorrelationRow,
    EloRatingRow,
    EventDetailResponse,
    EventLineupItem,
    EventListResponse,
    EventStatistic,
    EventSummary,
    EventTimelineItem,
    Forecast,
    FormRow,
    HealthResponse,
    LeagueTitleOutlook,
    Match,
    MatchCentreDetailResponse,
    MatchFactorSummary,
    MatchListResponse,
    OverviewResponse,
    PageMeta,
    PlayerListResponse,
    PlayerProfileResponse,
    PlayerStat,
    PlayerSummary,
    PredictionsResponse,
    QualityCell,
    QualityResponse,
    RankingRow,
    ReferenceStandingRow,
    RefereeSummary,
    SeasonCoverage,
    ShotAnalysisResponse,
    ShotCoverageRow,
    ShotEfficiencyRow,
    SourceMeta,
    StandingsResponse,
    Team,
    TeamListResponse,
    TeamRef,
    TournamentGoal,
    TournamentMatch,
    TournamentResponse,
    TournamentStage,
    TransferListResponse,
    TransferRow,
    canonical_team_id,
)
from football_analysis.api.db import ReadOnlyStore
from football_analysis.api.pagination import decode_cursor, encode_cursor
from football_analysis.config import (
    CALENDAR_YEAR_TOURNAMENTS,
    COMPETITIONS,
    LEAGUES,
    RECENT_LEAGUES,
    TOURNAMENTS,
    current_season,
    label,
    seasons,
)
from football_analysis.teams import display_team, team_key


API_SCHEMA_REVISION = "2026-09-15-match-centre-v1"


def _now() -> datetime:
    return datetime.now().replace(microsecond=0)


def _as_date(value) -> date | None:
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return None
    if pd.isna(value):
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    parsed = pd.to_datetime(value, errors="coerce")
    if pd.isna(parsed):
        return None
    return parsed.date()


def _as_datetime(value) -> datetime | None:
    if value is None or pd.isna(value):
        return None
    parsed = pd.to_datetime(value, errors="coerce")
    if pd.isna(parsed):
        return None
    return parsed.to_pydatetime().replace(microsecond=0)


def _mean(series: pd.Series) -> float | None:
    numeric = pd.to_numeric(series, errors="coerce")
    if numeric.dropna().empty:
        return None
    return float(numeric.mean())


def _search_text(value) -> str:
    text = unicodedata.normalize("NFKD", str(value or "")).encode("ascii", "ignore").decode()
    return " ".join(re.findall(r"[a-z0-9]+", text.casefold()))


def _fuzzy_score(query: str, value) -> float:
    """Small dependency-free typo score used by API-backed search fields."""
    needle, candidate = _search_text(query), _search_text(value)
    if not needle or not candidate:
        return 0.0
    if needle == candidate:
        return 1.0
    if needle in candidate:
        return 0.92 - min(candidate.index(needle), 20) / 200
    words = candidate.split()
    word_score = max((SequenceMatcher(None, needle, word).ratio() for word in words), default=0.0)
    return max(word_score, SequenceMatcher(None, needle, candidate).ratio())


def _has(store: ReadOnlyStore, name: str) -> bool:
    return name in store.tables()


def _source(name: str, coverage: str, freshness=None) -> SourceMeta:
    return SourceMeta(source=name, coverage=coverage, freshness=_as_datetime(freshness) or freshness)


def snapshot_etag(store: ReadOnlyStore) -> str:
    parts: list[str] = [API_SCHEMA_REVISION]
    tables = store.tables()
    for table, column in (
        ("ingestion_runs", "fetched_at"),
        ("recent_matches", "fetched_at"),
        ("tournament_matches", "fetched_at"),
        ("analytics_metadata", "refreshed_at"),
        ("prediction_models", "trained_at"),
        ("open_players", "fetched_at"),
        ("match_contexts", "fetched_at"),
    ):
        if table in tables:
            stamp = store.scalar(f"SELECT max({column}) FROM {table}")
            count = store.scalar(f"SELECT count(*) FROM {table}")
            parts.append(f"{table}:{count}:{stamp}")
    if "matches" in tables:
        parts.append(f"matches:{store.scalar('SELECT count(*) FROM matches')}")
    digest = hashlib.md5("|".join(parts).encode(), usedforsecurity=False).hexdigest()
    return f'"{digest}"'


def health(store: ReadOnlyStore | None) -> HealthResponse:
    if store is None:
        return HealthResponse(status="unavailable", database="missing", read_only=True)
    return HealthResponse(status="ok", database=str(store.path), read_only=True)


def _competition_media_map(store: ReadOnlyStore) -> dict[str, Any]:
    if not _has(store, "competition_media"):
        return {}
    df = store.query("SELECT league_code, badge_url, logo_url, banner_url, trophy_url, fanart_url FROM competition_media")
    return {row.league_code: row for row in df.itertuples(index=False)}


def _team_media_map(store: ReadOnlyStore) -> dict[str, Any]:
    if not _has(store, "team_media"):
        return {}
    df = store.query("SELECT team, badge_url, logo_url FROM team_media")
    return {canonical_team_id(row.team): row for row in df.itertuples(index=False)}


def _build_team_ref(name: str | None, media_map: dict[str, Any] | None = None) -> TeamRef:
    raw = name or ""
    tid = canonical_team_id(raw)
    badge = None
    logo = None
    if media_map and tid in media_map:
        badge = getattr(media_map[tid], "badge_url", None) or None
        logo = getattr(media_map[tid], "logo_url", None) or None
    return TeamRef(
        team_id=tid,
        name=display_team(raw) or raw,
        badge_url=badge,
        logo_url=logo,
    )


def catalog(store: ReadOnlyStore) -> CatalogResponse:
    live = current_season()
    completed = set(seasons())
    media_map = _competition_media_map(store)
    rows = []
    if _has(store, "matches"):
        rows.append(store.query(
            "SELECT league AS competition, season, count(*) AS match_count, max(match_date) AS latest_match "
            "FROM matches GROUP BY 1, 2"
        ))
    if _has(store, "recent_matches"):
        rows.append(store.query(
            "SELECT league AS competition, season, count(*) AS match_count, max(match_date) AS latest_match "
            "FROM recent_matches GROUP BY 1, 2"
        ))
    if _has(store, "tournament_matches"):
        rows.append(store.query(
            "SELECT competition, season, count(*) AS match_count, max(match_date) AS latest_match "
            "FROM tournament_matches GROUP BY 1, 2"
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
            code=code, name=name, kind=kind, seasons=season_rows,
            source=_source("football-data.co.uk" if kind == "domestic" else "openfootball", "loaded", freshness),
            badge_url=getattr(media, "badge_url", None) or None,
            logo_url=getattr(media, "logo_url", None) or None,
            banner_url=getattr(media, "banner_url", None) or None,
            trophy_url=getattr(media, "trophy_url", None) or None,
            fanart_url=getattr(media, "fanart_url", None) or None,
        ))
    return CatalogResponse(
        competitions=competitions,
        current_season=live,
        generated_at=_now(),
        source=_source("duckdb", "catalog", freshness),
    )


def list_teams(store: ReadOnlyStore, competition: str | None, season: int | None) -> TeamListResponse:
    if not (_has(store, "team_seasons") or _has(store, "recent_matches") or _has(store, "tournament_matches")):
        return TeamListResponse(teams=[], source=_source("duckdb", "empty"))

    # Unified query combining historical team_seasons, live recent_matches, and tournament_matches
    q = """
    WITH all_season_teams AS (
        -- Historical team_seasons
        SELECT league, season, team, played, points FROM team_seasons
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
        WHERE NOT EXISTS (SELECT 1 FROM team_seasons ts WHERE ts.league = m.league AND ts.season = m.season)
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
            FROM tournament_matches
            UNION ALL
            SELECT competition, season, away_team AS team, home_goals, away_goals,
                   CASE WHEN away_goals > home_goals THEN 3 WHEN away_goals = home_goals THEN 1 ELSE 0 END AS points
            FROM tournament_matches
        ) t
        WHERE NOT EXISTS (SELECT 1 FROM team_seasons ts WHERE ts.league = t.competition AND ts.season = t.season)
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
            SELECT league, team FROM team_seasons WHERE league = ?
            UNION
            SELECT league, home_team AS team FROM recent_matches WHERE league = ?
            UNION
            SELECT league, away_team AS team FROM recent_matches WHERE league = ?
            UNION
            SELECT competition AS league, home_team AS team FROM tournament_matches WHERE competition = ?
            UNION
            SELECT competition AS league, away_team AS team FROM tournament_matches WHERE competition = ?
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
    return TeamListResponse(teams=teams, source=_source("duckdb", "teams"))


def _match_from_row(row, competition_field="league", media_map: dict[str, Any] | None = None) -> Match:
    _sentinel = object()
    competition = getattr(row, competition_field, _sentinel)
    if competition is _sentinel:
        competition = getattr(row, "competition", getattr(row, "league", None))
    return Match(
        competition=competition,
        season=int(row.season),
        match_date=_as_date(row.match_date) or date.min,
        home=_build_team_ref(row.home_team, media_map),
        away=_build_team_ref(row.away_team, media_map),
        home_goals=None if pd.isna(getattr(row, "home_goals", None)) else int(row.home_goals),
        away_goals=None if pd.isna(getattr(row, "away_goals", None)) else int(row.away_goals),
        venue=getattr(row, "venue", None),
        stage=getattr(row, "stage", None),
        referee=None if pd.isna(getattr(row, "referee", None)) else getattr(row, "referee", None),
        home_shots=None if pd.isna(getattr(row, "home_shots", None)) else int(row.home_shots),
        away_shots=None if pd.isna(getattr(row, "away_shots", None)) else int(row.away_shots),
        home_shots_on_target=None if pd.isna(getattr(row, "home_sot", None)) else int(row.home_sot),
        away_shots_on_target=None if pd.isna(getattr(row, "away_sot", None)) else int(row.away_sot),
        half_time_home_goals=None if pd.isna(getattr(row, "half_time_home_goals", None)) else int(row.half_time_home_goals),
        half_time_away_goals=None if pd.isna(getattr(row, "half_time_away_goals", None)) else int(row.half_time_away_goals),
        home_corners=None if pd.isna(getattr(row, "home_corners", None)) else int(row.home_corners),
        away_corners=None if pd.isna(getattr(row, "away_corners", None)) else int(row.away_corners),
        home_fouls=None if pd.isna(getattr(row, "home_fouls", None)) else int(row.home_fouls),
        away_fouls=None if pd.isna(getattr(row, "away_fouls", None)) else int(row.away_fouls),
        home_yellows=None if pd.isna(getattr(row, "home_yellows", None)) else int(row.home_yellows),
        away_yellows=None if pd.isna(getattr(row, "away_yellows", None)) else int(row.away_yellows),
        home_reds=None if pd.isna(getattr(row, "home_reds", None)) else int(row.home_reds),
        away_reds=None if pd.isna(getattr(row, "away_reds", None)) else int(row.away_reds),
        source=getattr(row, "source", None),
    )


def list_matches(
    store: ReadOnlyStore,
    competition: str | None = None,
    season: int | None = None,
    team: str | None = None,
    venue: str | None = None,
    cursor: str | None = None,
    limit: int = 50,
) -> MatchListResponse:
    limit = max(1, min(int(limit), 200))
    frames = []
    if _has(store, "matches"):
        frames.append(store.query(
            "SELECT league AS competition, season, match_date, home_team, away_team, "
            "home_goals, away_goals, home_shots, away_shots, home_sot, away_sot, "
            "half_time_home_goals, half_time_away_goals, home_corners, away_corners, "
            "home_fouls, away_fouls, home_yellows, away_yellows, home_reds, away_reds, "
            "referee, CAST(NULL AS VARCHAR) AS stage, "
            "CAST(NULL AS VARCHAR) AS venue, 'football-data.co.uk' AS source FROM matches"
        ))
    if _has(store, "recent_matches"):
        frames.append(store.query(
            "SELECT league AS competition, season, match_date, home_team, away_team, "
            "home_goals, away_goals, home_shots, away_shots, home_sot, away_sot, "
            "half_time_home_goals, half_time_away_goals, home_corners, away_corners, "
            "home_fouls, away_fouls, home_yellows, away_yellows, home_reds, away_reds, "
            "referee, CAST(NULL AS VARCHAR) AS stage, "
            "CAST(NULL AS VARCHAR) AS venue, source FROM recent_matches"
        ))
    if _has(store, "tournament_matches"):
        frames.append(store.query(
            "SELECT competition, season, match_date, home_team, away_team, "
            "home_goals, away_goals, CAST(NULL AS INTEGER) AS home_shots, "
            "CAST(NULL AS INTEGER) AS away_shots, CAST(NULL AS INTEGER) AS home_sot, "
            "CAST(NULL AS INTEGER) AS away_sot, CAST(NULL AS INTEGER) AS half_time_home_goals, "
            "CAST(NULL AS INTEGER) AS half_time_away_goals, CAST(NULL AS INTEGER) AS home_corners, "
            "CAST(NULL AS INTEGER) AS away_corners, CAST(NULL AS INTEGER) AS home_fouls, "
            "CAST(NULL AS INTEGER) AS away_fouls, CAST(NULL AS INTEGER) AS home_yellows, "
            "CAST(NULL AS INTEGER) AS away_yellows, CAST(NULL AS INTEGER) AS home_reds, "
            "CAST(NULL AS INTEGER) AS away_reds, CAST(NULL AS VARCHAR) AS referee, stage, venue, source "
            "FROM tournament_matches"
        ))
    if not frames:
        return MatchListResponse(
            matches=[], page=PageMeta(next_cursor=None, limit=limit, returned=0),
            source=_source("duckdb", "empty"),
        )
    frame = pd.concat(frames, ignore_index=True)
    frame["match_date"] = pd.to_datetime(frame.match_date)
    if competition:
        frame = frame[frame.competition == competition]
    if season is not None:
        frame = frame[frame.season == season]
    if team:
        key = team_key(team) or team
        home_keys = frame.home_team.map(team_key)
        away_keys = frame.away_team.map(team_key)
        frame = frame[(home_keys == key) | (away_keys == key) | (frame.home_team == team) | (frame.away_team == team)]
        if venue == "Home":
            frame = frame[home_keys == key]
        elif venue == "Away":
            frame = frame[away_keys == key]
    elif venue:
        frame = frame[frame.venue == venue]
    frame = frame.sort_values(
        ["match_date", "competition", "home_team", "away_team"],
        ascending=[False, True, True, True],
    ).reset_index(drop=True)
    token = decode_cursor(cursor)
    if token:
        cursor_date = pd.Timestamp(token["d"])
        mask = (
            (frame.match_date < cursor_date)
            | ((frame.match_date == cursor_date) & (frame.competition > token["c"]))
            | (
                (frame.match_date == cursor_date)
                & (frame.competition == token["c"])
                & (frame.home_team > token["h"])
            )
            | (
                (frame.match_date == cursor_date)
                & (frame.competition == token["c"])
                & (frame.home_team == token["h"])
                & (frame.away_team > token["a"])
            )
        )
        frame = frame[mask]
    page = frame.head(limit + 1)
    has_more = len(page) > limit
    page = page.head(limit)
    next_cursor = None
    if has_more and not page.empty:
        last = page.iloc[-1]
        next_cursor = encode_cursor({
            "d": pd.Timestamp(last.match_date).strftime("%Y-%m-%d"),
            "c": last.competition,
            "h": last.home_team,
            "a": last.away_team,
        })
    tm_map = _team_media_map(store)
    matches = [_match_from_row(row, "competition", tm_map) for row in page.itertuples(index=False)]
    return MatchListResponse(
        matches=matches,
        page=PageMeta(next_cursor=next_cursor, limit=limit, returned=len(matches)),
        source=_source("duckdb", "matches"),
    )


def shot_analysis(
    store: ReadOnlyStore,
    competition: str | None = None,
    season: int | None = None,
    team: str | None = None,
) -> ShotAnalysisResponse:
    """Expose nullable shot analysis only after the 95% coverage gate."""
    frames = []
    for table in ("matches", "recent_matches"):
        if _has(store, table):
            frames.append(store.query(
                f"SELECT league AS competition, season, home_shots, away_shots, home_sot, away_sot FROM {table}"
            ))
    raw = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    if not raw.empty:
        if competition:
            raw = raw[raw.competition == competition]
        if season is not None:
            raw = raw[raw.season == season]
        raw["complete"] = raw[["home_shots", "away_shots", "home_sot", "away_sot"]].notna().all(axis=1)
        grouped = raw.groupby(["competition", "season"], as_index=False).agg(
            matches=("complete", "size"), shot_matches=("complete", "sum"),
        )
        grouped["coverage_pct"] = 100 * grouped.shot_matches / grouped.matches
        coverage = [
            ShotCoverageRow(
                competition=row.competition,
                season=int(row.season),
                matches=int(row.matches),
                shot_matches=int(row.shot_matches),
                coverage_pct=float(row.coverage_pct),
            )
            for row in grouped.itertuples(index=False)
        ]
    else:
        coverage = []

    rows: list[ShotEfficiencyRow] = []
    if _has(store, "shot_efficiency_cache"):
        sql = "SELECT * FROM shot_efficiency_cache WHERE coverage_pct >= 95"
        values: list[Any] = []
        if competition:
            sql += " AND league = ?"
            values.append(competition)
        if season is not None:
            sql += " AND season = ?"
            values.append(season)
        sql += " ORDER BY season DESC, shots_per_match DESC NULLS LAST, team"
        frame = store.query(sql, values)
        if team and not frame.empty:
            wanted = team_key(team) or team
            frame = frame[(frame.team.map(team_key) == wanted) | (frame.team == team)]
        media = _team_media_map(store)
        rows = [
            ShotEfficiencyRow(
                competition=row.league,
                season=int(row.season),
                team=_build_team_ref(row.team, media),
                matches=int(row.matches),
                coverage_pct=float(row.coverage_pct),
                shots_per_match=None if pd.isna(row.shots_per_match) else float(row.shots_per_match),
                shot_accuracy_pct=None if pd.isna(row.shot_accuracy_pct) else float(row.shot_accuracy_pct),
                goals_per_shot_pct=None if pd.isna(row.goals_per_shot_pct) else float(row.goals_per_shot_pct),
                goals_per_sot_pct=None if pd.isna(row.goals_per_sot_pct) else float(row.goals_per_sot_pct),
            )
            for row in frame.itertuples(index=False)
        ]
    return ShotAnalysisResponse(
        coverage=coverage,
        teams=rows,
        source=_source("football-data.co.uk", "95% complete-field gate"),
    )


def list_event_details(
    store: ReadOnlyStore,
    competition: str | None = None,
    season: int | None = None,
) -> EventListResponse:
    if not _has(store, "recent_events"):
        return EventListResponse(events=[], source=_source("TheSportsDB", "empty"))
    frame = store.query("SELECT * FROM recent_events ORDER BY match_date DESC, event_id")
    if competition:
        frame = frame[frame.league == competition]
    if season is not None:
        frame = frame[frame.season == season]
    counts: dict[str, dict[str, int]] = {}
    for table, key in (
        ("event_statistics", "statistics_count"),
        ("event_timeline", "timeline_count"),
        ("event_lineups", "lineup_count"),
    ):
        if _has(store, table):
            count_frame = store.query(f"SELECT event_id, count(*) AS count FROM {table} GROUP BY event_id")
            for row in count_frame.itertuples(index=False):
                counts.setdefault(str(row.event_id), {})[key] = int(row.count)
    media = _team_media_map(store)
    events = []
    for row in frame.itertuples(index=False):
        event_counts = counts.get(str(row.event_id), {})
        if not event_counts:
            continue
        events.append(EventSummary(
            event_id=str(row.event_id),
            competition=row.league,
            season=int(row.season),
            match_date=_as_date(row.match_date) or date.min,
            home=_build_team_ref(row.home_team, media),
            away=_build_team_ref(row.away_team, media),
            home_goals=None if pd.isna(row.home_goals) else int(row.home_goals),
            away_goals=None if pd.isna(row.away_goals) else int(row.away_goals),
            status=None if pd.isna(row.status) else row.status,
            statistics_count=event_counts.get("statistics_count", 0),
            timeline_count=event_counts.get("timeline_count", 0),
            lineup_count=event_counts.get("lineup_count", 0),
        ))
    return EventListResponse(
        events=events,
        source=_source("TheSportsDB", "capped event-detail samples"),
    )


def event_detail(store: ReadOnlyStore, event_id: str) -> EventDetailResponse | None:
    listing = list_event_details(store)
    summary = next((event for event in listing.events if event.event_id == str(event_id)), None)
    if summary is None:
        return None
    media = _team_media_map(store)
    stats = store.query(
        "SELECT statistic, home_value, away_value FROM event_statistics WHERE event_id = ? ORDER BY statistic",
        [str(event_id)],
    ) if _has(store, "event_statistics") else pd.DataFrame()
    timeline = store.query(
        "SELECT * FROM event_timeline WHERE event_id = ? ORDER BY try_cast(minute AS INTEGER) NULLS LAST, timeline_id",
        [str(event_id)],
    ) if _has(store, "event_timeline") else pd.DataFrame()
    lineups = store.query(
        "SELECT * FROM event_lineups WHERE event_id = ? ORDER BY is_home DESC, is_substitute, team, player",
        [str(event_id)],
    ) if _has(store, "event_lineups") else pd.DataFrame()
    return EventDetailResponse(
        event=summary,
        statistics=[EventStatistic(
            statistic=row.statistic,
            home_value=None if pd.isna(row.home_value) else float(row.home_value),
            away_value=None if pd.isna(row.away_value) else float(row.away_value),
        ) for row in stats.itertuples(index=False)],
        timeline=[EventTimelineItem(
            minute=None if pd.isna(row.minute) else str(row.minute),
            event_type=None if pd.isna(row.event_type) else row.event_type,
            detail=None if pd.isna(row.detail) else row.detail,
            team=_build_team_ref(row.team, media),
            player_id=None if pd.isna(row.player_id) else str(row.player_id),
            player=None if pd.isna(row.player) else row.player,
            assist=None if pd.isna(row.assist) else row.assist,
            is_home=None if pd.isna(row.is_home) else bool(row.is_home),
            comment=None if pd.isna(row.comment) else row.comment,
        ) for row in timeline.itertuples(index=False)],
        lineups=[EventLineupItem(
            team=_build_team_ref(row.team, media),
            player_id=None if pd.isna(row.player_id) else str(row.player_id),
            player=None if pd.isna(row.player) else row.player,
            position=None if pd.isna(row.position) else row.position,
            is_home=None if pd.isna(row.is_home) else bool(row.is_home),
            is_substitute=None if pd.isna(row.is_substitute) else bool(row.is_substitute),
            shirt_number=None if pd.isna(row.shirt_number) else str(row.shirt_number),
            cutout_url=None if pd.isna(row.cutout_url) else row.cutout_url,
        ) for row in lineups.itertuples(index=False)],
        source=_source("TheSportsDB", "free endpoint samples; collections capped at five"),
    )


def _present(value) -> str | None:
    if value is None or pd.isna(value):
        return None
    text = str(value).strip()
    return text or None


def _match_narrative(
    match: Match,
    statistics: list[EventStatistic],
    timeline: list[EventTimelineItem],
    home_formation: str | None,
    away_formation: str | None,
) -> list[str]:
    """Build a factual overview from stored values without inventing match events."""
    story: list[str] = []
    if match.home_goals is not None and match.away_goals is not None:
        if match.home_goals == match.away_goals:
            story.append(f"{match.home.name} and {match.away.name} finished level at {match.home_goals}–{match.away_goals}.")
        else:
            winner = match.home.name if match.home_goals > match.away_goals else match.away.name
            story.append(f"{winner} won {match.home_goals}–{match.away_goals}.")
    if match.half_time_home_goals is not None and match.half_time_away_goals is not None:
        second_half_goals = (
            (match.home_goals or 0) + (match.away_goals or 0)
            - match.half_time_home_goals - match.half_time_away_goals
        )
        story.append(
            f"The half-time score was {match.half_time_home_goals}–{match.half_time_away_goals}; "
            f"the second half added {second_half_goals} {'goal' if second_half_goals == 1 else 'goals'}."
        )
    total_attempt_labels = {"shots", "total shots", "total attempts"}
    shot = next((item for item in statistics if item.statistic.casefold().strip() in total_attempt_labels), None)
    if shot and shot.home_value is not None and shot.away_value is not None:
        leader = match.home.name if shot.home_value > shot.away_value else match.away.name if shot.away_value > shot.home_value else None
        story.append(
            f"{leader + ' led' if leader else 'The teams were level'} in total attempts, "
            f"{shot.home_value:g} to {shot.away_value:g}."
        )
    goals = [item for item in timeline if "goal" in (item.event_type or "").casefold()]
    if goals:
        scorers = ", ".join(
            f"{item.player or item.team.name} {item.minute + '′' if item.minute else ''}".strip()
            for item in goals[:4]
        )
        story.append(f"Recorded scoring events: {scorers}.")
    if home_formation or away_formation:
        story.append(
            f"Published shapes: {match.home.name} {home_formation or 'not supplied'}; "
            f"{match.away.name} {away_formation or 'not supplied'}."
        )
    return story


def match_centre_detail(
    store: ReadOnlyStore,
    competition: str,
    season: int,
    match_date: str,
    home: str,
    away: str,
) -> MatchCentreDetailResponse | None:
    """Return the richest verified detail available for any match shown in the app."""
    try:
        wanted_date = pd.Timestamp(match_date).date()
    except (TypeError, ValueError):
        return None
    listing = list_matches(store, competition, season, home, None, None, 200)
    wanted_home, wanted_away = team_key(home), team_key(away)
    match = next((
        item for item in listing.matches
        if item.match_date == wanted_date
        and team_key(item.home.name) == wanted_home
        and team_key(item.away.name) == wanted_away
    ), None)
    if match is None:
        return None

    context = None
    if _has(store, "match_contexts"):
        candidates = store.query(
            "SELECT * FROM match_contexts WHERE match_date = ? ORDER BY fetched_at DESC",
            [wanted_date],
        )
        for row in candidates.itertuples(index=False):
            if team_key(row.home_team) == wanted_home and team_key(row.away_team) == wanted_away:
                context = row
                break

    event_row = None
    if _has(store, "recent_events"):
        candidates = store.query(
            "SELECT * FROM recent_events WHERE league = ? AND season = ? AND match_date = ? ORDER BY fetched_at DESC",
            [competition, season, wanted_date],
        )
        for row in candidates.itertuples(index=False):
            if team_key(row.home_team) == wanted_home and team_key(row.away_team) == wanted_away:
                event_row = row
                break

    event_id = str(event_row.event_id) if event_row is not None else None
    provider_detail = event_detail(store, event_id) if event_id else None
    statistics = list(provider_detail.statistics) if provider_detail else []
    known_stats = {item.statistic.casefold() for item in statistics}
    stored_statistics = (
        ("Shots", match.home_shots, match.away_shots),
        ("Shots on target", match.home_shots_on_target, match.away_shots_on_target),
        ("Corners", match.home_corners, match.away_corners),
        ("Fouls", match.home_fouls, match.away_fouls),
        ("Yellow cards", match.home_yellows, match.away_yellows),
        ("Red cards", match.home_reds, match.away_reds),
        ("Half-time goals", match.half_time_home_goals, match.half_time_away_goals),
    )
    for label, home_value, away_value in stored_statistics:
        if (home_value is not None or away_value is not None) and label.casefold() not in known_stats:
            statistics.append(EventStatistic(
                statistic=label,
                home_value=None if home_value is None else float(home_value),
                away_value=None if away_value is None else float(away_value),
            ))

    timeline = list(provider_detail.timeline) if provider_detail else []
    if not timeline and competition in TOURNAMENTS and _has(store, "tournament_goals"):
        goals = store.query(
            "SELECT * FROM tournament_goals WHERE competition = ? AND season = ? AND match_date = ?",
            [competition, season, wanted_date],
        )
        media = _team_media_map(store)
        goal_rows = []
        for row in goals.itertuples(index=False):
            if team_key(row.team) not in {wanted_home, wanted_away}:
                continue
            detail = "Penalty" if bool(row.penalty) else "Own goal" if bool(row.own_goal) else "Open play"
            goal_rows.append(EventTimelineItem(
                minute=_present(row.minute), event_type="Goal", detail=detail,
                team=_build_team_ref(row.team, media), player=_present(row.player),
                is_home=team_key(row.team) == wanted_home,
            ))
        timeline = sorted(goal_rows, key=lambda item: int("".join(filter(str.isdigit, item.minute or "999")) or 999))

    lineups = list(provider_detail.lineups) if provider_detail else []
    home_starters = sum(item.is_home is True and item.is_substitute is not True for item in lineups)
    away_starters = sum(item.is_home is False and item.is_substitute is not True for item in lineups)
    lineup_complete = home_starters >= 11 and away_starters >= 11
    home_coach = _present(getattr(context, "home_coach", None)) or _present(getattr(event_row, "home_coach", None))
    away_coach = _present(getattr(context, "away_coach", None)) or _present(getattr(event_row, "away_coach", None))
    home_formation = _present(getattr(context, "home_formation", None)) or _present(getattr(event_row, "home_formation", None))
    away_formation = _present(getattr(context, "away_formation", None)) or _present(getattr(event_row, "away_formation", None))
    stadium = (
        match.venue
        or _present(getattr(context, "stadium", None))
        or _present(getattr(event_row, "venue", None))
    )
    attendance_value = getattr(context, "attendance", None)
    if attendance_value is None or pd.isna(attendance_value):
        attendance_value = getattr(event_row, "attendance", None)
    attendance = None if attendance_value is None or pd.isna(attendance_value) else int(attendance_value)
    referee = (
        match.referee
        or _present(getattr(context, "referee", None))
        or _present(getattr(event_row, "referee", None))
    )
    if referee != match.referee or stadium != match.venue:
        match = match.model_copy(update={"referee": referee, "venue": stadium})

    coverage_notes = []
    if not lineups:
        coverage_notes.append("No verified lineup was supplied for this match.")
    elif not lineup_complete:
        coverage_notes.append(f"The provider supplied {len(lineups)} lineup rows; the pitch shows only those verified players.")
    if not home_formation or not away_formation:
        coverage_notes.append("At least one published formation is unavailable.")
    if not timeline:
        coverage_notes.append("No event timeline was supplied.")

    source_names = [match.source or "match store"]
    if context is not None:
        source_names.append("Transfermarkt Open Dataset")
    if provider_detail or event_row is not None:
        source_names.append("TheSportsDB")
    return MatchCentreDetailResponse(
        match=match,
        event_id=event_id,
        status=_present(getattr(event_row, "status", None)),
        home_coach=home_coach,
        away_coach=away_coach,
        home_formation=home_formation,
        away_formation=away_formation,
        stadium=stadium,
        attendance=attendance,
        statistics=statistics,
        timeline=timeline,
        lineups=lineups,
        narrative=_match_narrative(match, statistics, timeline, home_formation, away_formation),
        lineup_complete=lineup_complete,
        coverage_notes=coverage_notes,
        source=_source(" + ".join(dict.fromkeys(source_names)), "verified fields available for this match"),
    )


def _load_analysis_matches(store: ReadOnlyStore) -> pd.DataFrame:
    parts = []
    if _has(store, "team_matches"):
        parts.append(store.query("SELECT * FROM team_matches"))
    if _has(store, "recent_matches"):
        recent = store.query(
            "SELECT league, season, match_date, home_team, away_team, home_goals, away_goals, "
            "home_shots, away_shots, home_sot, away_sot FROM recent_matches"
        )
        if not recent.empty:
            home = pd.DataFrame({
                "league": recent.league, "season": recent.season, "match_date": recent.match_date,
                "team": recent.home_team, "opponent": recent.away_team, "venue": "Home",
                "gf": recent.home_goals, "ga": recent.away_goals,
                "shots": recent.home_shots, "shots_on_target": recent.home_sot,
            })
            away = pd.DataFrame({
                "league": recent.league, "season": recent.season, "match_date": recent.match_date,
                "team": recent.away_team, "opponent": recent.home_team, "venue": "Away",
                "gf": recent.away_goals, "ga": recent.home_goals,
                "shots": recent.away_shots, "shots_on_target": recent.away_sot,
            })
            expanded = pd.concat([home, away], ignore_index=True)
            expanded["points"] = np.where(
                expanded.gf > expanded.ga, 3, np.where(expanded.gf == expanded.ga, 1, 0)
            )
            parts.append(expanded)
    if _has(store, "tournament_matches"):
        tourney = store.query("SELECT * FROM tournament_matches")
        if not tourney.empty:
            parts.append(tournament_team_matches(tourney))
    if not parts:
        return pd.DataFrame(columns=[
            "league", "season", "match_date", "team", "opponent", "venue", "gf", "ga", "points",
        ])
    frame = pd.concat(parts, ignore_index=True)
    return frame.drop_duplicates(["league", "season", "match_date", "team", "opponent", "venue"])


def _resolve_teams(frame: pd.DataFrame, requested: list[str]) -> list[str]:
    if not requested:
        return []
    keys = {team_key(name) or name: name for name in frame.team.unique()}
    resolved = []
    for value in requested:
        key = team_key(value) or value
        if value in set(frame.team):
            resolved.append(value)
        elif key in keys:
            resolved.append(keys[key])
        else:
            resolved.append(value)
    return resolved


def _factor_summary(store: ReadOnlyStore, filters: AnalysisFilters) -> MatchFactorSummary:
    if not _has(store, "matches"):
        return MatchFactorSummary()
    fixtures = store.query("SELECT * FROM matches")
    if _has(store, "recent_matches"):
        recent = store.query("SELECT * FROM recent_matches")
        if not recent.empty:
            fixtures = pd.concat([fixtures, recent], ignore_index=True)
    if fixtures.empty:
        return MatchFactorSummary()
    if filters.competitions:
        fixtures = fixtures[fixtures.league.isin(filters.competitions)]
    if filters.seasons:
        fixtures = fixtures[fixtures.season.isin(filters.seasons)]
    factors = team_match_factors(fixtures)
    if filters.teams:
        wanted = {team_key(name) or name for name in filters.teams}
        factors = factors[factors.team.map(team_key).isin(wanted) | factors.team.isin(filters.teams)]
    if filters.venue:
        factors = factors[factors.venue == filters.venue]
    if factors.empty:
        return MatchFactorSummary()
    referees = []
    named = factors[factors.referee.fillna("") != ""]
    if not named.empty:
        grouped = named.groupby("referee", as_index=False).agg(
            matches=("referee", "size"),
            yellow_cards_mean=("yellow_cards", "mean"),
            red_cards_mean=("red_cards", "mean"),
        ).sort_values("matches", ascending=False).head(8)
        referees = [
            RefereeSummary(
                referee=row.referee,
                matches=int(row.matches),
                yellow_cards_mean=None if pd.isna(row.yellow_cards_mean) else float(row.yellow_cards_mean),
                red_cards_mean=None if pd.isna(row.red_cards_mean) else float(row.red_cards_mean),
            )
            for row in grouped.itertuples(index=False)
        ]
    return MatchFactorSummary(
        first_half_goals_mean=_mean(factors.first_half_goals),
        second_half_goals_mean=_mean(factors.second_half_goals),
        corners_mean=_mean(factors.corners),
        fouls_mean=_mean(factors.fouls),
        yellow_cards_mean=_mean(factors.yellow_cards),
        red_cards_mean=_mean(factors.red_cards),
        referees=referees,
    )


def build_analysis(store: ReadOnlyStore, body: AnalysisFilters) -> AnalysisReportResponse:
    tm_map = _team_media_map(store)
    matches = _load_analysis_matches(store)
    teams = _resolve_teams(matches, body.teams)
    request = AnalysisRequest(
        competitions=tuple(body.competitions),
        seasons=tuple(body.seasons),
        teams=tuple(teams),
        venue=body.venue,
        form_window=body.form_window,
    )
    report = AnalysisSystem(matches).build_report(request) if not matches.empty else AnalysisSystem(
        pd.DataFrame(columns=[
            "league", "season", "match_date", "team", "opponent", "venue", "gf", "ga", "points",
        ])
    ).build_report(request)
    rankings = []
    for row in report.rankings.itertuples(index=False):
        rankings.append(RankingRow(
            competition=row.league, season=int(row.season), team=_build_team_ref(row.team, tm_map),
            rank=int(row.rank), played=int(row.played), wins=int(row.wins), draws=int(row.draws),
            losses=int(row.losses), points=int(row.points), goals_for=int(row.goals_for),
            goals_against=int(row.goals_against), goal_difference=int(row.goal_difference),
            points_per_game=float(row.points_per_game), goals_per_game=float(row.goals_per_game),
            conceded_per_game=float(row.conceded_per_game), win_rate=float(row.win_rate),
            clean_sheet_rate=float(row.clean_sheet_rate),
            form=None if pd.isna(getattr(row, "form", None)) else str(row.form),
            form_ppg=None if pd.isna(getattr(row, "form_ppg", None)) else float(row.form_ppg),
        ))
    form = [
        FormRow(
            competition=row.league, season=int(row.season), team=_build_team_ref(row.team, tm_map),
            form_matches=int(row.form_matches), form_points=int(row.form_points),
            form_goals_for=int(row.form_goals_for), form_goals_against=int(row.form_goals_against),
            form=str(row.form), form_ppg=float(row.form_ppg),
        )
        for row in report.form.itertuples(index=False)
    ]
    correlations = []
    if not report.correlations.empty:
        for record in report.correlations.replace({np.nan: None}).to_dict("records"):
            correlations.append(CorrelationRow.model_validate(record))

    elo_ratings = []
    if _has(store, "elo_ratings"):
        elo_sql = "SELECT league, season, team, post_elo FROM elo_ratings"
        clauses = []
        params = []
        if body.competitions:
            placeholders = ", ".join("?" for _ in body.competitions)
            clauses.append(f"league IN ({placeholders})")
            params.extend(body.competitions)
        if body.seasons:
            placeholders = ", ".join("?" for _ in body.seasons)
            clauses.append(f"season IN ({placeholders})")
            params.extend(body.seasons)
        if body.teams:
            resolved_teams = _resolve_teams(matches, body.teams) if not matches.empty else body.teams
            placeholders = ", ".join("?" for _ in resolved_teams)
            clauses.append(f"team IN ({placeholders})")
            params.extend(resolved_teams)
        if clauses:
            elo_sql += " WHERE " + " AND ".join(clauses)
        elo_sql += " ORDER BY match_date DESC"

        elo_df = store.query(elo_sql, params)
        if not elo_df.empty:
            latest_elo = elo_df.drop_duplicates(subset=["league", "season", "team"], keep="first")
            for erow in latest_elo.itertuples(index=False):
                elo_ratings.append(EloRatingRow(
                    team=_build_team_ref(erow.team, tm_map),
                    season=int(erow.season),
                    league=erow.league,
                    post_elo=round(float(erow.post_elo), 1),
                ))

    return AnalysisReportResponse(
        filters=body,
        match_count=int(len(report.matches)),
        rankings=rankings,
        form=form,
        correlations=correlations,
        match_factors=_factor_summary(store, body),
        elo_ratings=elo_ratings,
        source=_source("analysis-system", "rankings+form+correlations+elo"),
    )


def standings(
    store: ReadOnlyStore,
    competition: str,
    season: int,
    form_window: int = 5,
    venue: str | None = None,
) -> StandingsResponse:
    """Return the results-derived table and the optional external validation table."""
    report = build_analysis(store, AnalysisFilters(
        competitions=[competition], seasons=[season], form_window=form_window, venue=venue,
    ))
    derived = {team_key(row.team.name): row for row in report.rankings}
    reference_rows: list[ReferenceStandingRow] = []
    freshness = None
    if _has(store, "reference_standings"):
        frame = store.query(
            "SELECT * FROM reference_standings WHERE league = ? AND season = ? ORDER BY rank",
            [competition, season],
        )
        if not frame.empty:
            freshness = frame.fetched_at.max()
        media = _team_media_map(store)
        for row in frame.itertuples(index=False):
            result = derived.get(team_key(row.team))
            ref_points = None if pd.isna(row.points) else int(row.points)
            result_points = result.points if result else None
            ref_rank = int(row.rank)
            result_rank = result.rank if result else None
            reference_rows.append(ReferenceStandingRow(
                competition=competition,
                season=season,
                source_name=row.source,
                rank=ref_rank,
                team=_build_team_ref(row.team, media),
                played=None if pd.isna(row.played) else int(row.played),
                points=ref_points,
                goal_difference=None if pd.isna(row.goal_difference) else int(row.goal_difference),
                form=None if pd.isna(row.form) else str(row.form),
                description=None if pd.isna(row.description) else str(row.description),
                source_updated_at=_as_datetime(row.source_updated_at),
                fetched_at=_as_datetime(row.fetched_at),
                results_rank=result_rank,
                results_points=result_points,
                results_goal_difference=result.goal_difference if result else None,
                point_adjustment=(ref_points - result_points) if ref_points is not None and result_points is not None else None,
                rank_difference=(ref_rank - result_rank) if result_rank is not None else None,
            ))
    return StandingsResponse(
        competition=competition,
        season=season,
        rankings=report.rankings,
        reference=reference_rows,
        source=_source("analysis-system+reference", "results-derived and external validation", freshness),
    )


def tournament(store: ReadOnlyStore, competition: str, season: int) -> TournamentResponse:
    name = TOURNAMENTS.get(competition, COMPETITIONS.get(competition, competition))
    if not _has(store, "tournament_matches"):
        return TournamentResponse(
            competition=competition, name=name, season=season,
            stages=[], matches=[], scorers=[],
            source=_source("openfootball", "empty"),
        )
    matches = store.query(
        "SELECT * FROM tournament_matches WHERE competition = ? AND season = ? ORDER BY match_date, home_team",
        [competition, season],
    )
    stages = []
    if not matches.empty:
        grouped = matches.groupby("stage", as_index=False).size().rename(columns={"size": "match_count"})
        stages = [TournamentStage(stage=row.stage, match_count=int(row.match_count)) for row in grouped.itertuples(index=False)]
    tm_map = _team_media_map(store)
    payload = []
    for row in matches.itertuples(index=False):
        payload.append(TournamentMatch(
            competition=row.competition, season=int(row.season),
            match_date=_as_date(row.match_date) or date.min,
            home=_build_team_ref(row.home_team, tm_map), away=_build_team_ref(row.away_team, tm_map),
            home_goals=int(row.home_goals), away_goals=int(row.away_goals),
            venue=row.venue, stage=row.stage, source=row.source,
            group_name=None if pd.isna(row.group_name) else row.group_name,
            home_penalties=None if pd.isna(row.home_penalties) else int(row.home_penalties),
            away_penalties=None if pd.isna(row.away_penalties) else int(row.away_penalties),
            status=row.status,
        ))
    scorers = []
    if _has(store, "tournament_goals"):
        goals = store.query(
            "SELECT * FROM tournament_goals WHERE competition = ? AND season = ? ORDER BY match_date, player",
            [competition, season],
        )
        scorers = [
            TournamentGoal(
                match_date=_as_date(row.match_date) or date.min,
                team=_build_team_ref(row.team, tm_map), player=row.player,
                minute=None if pd.isna(row.minute) else str(row.minute),
                penalty=bool(row.penalty), own_goal=bool(row.own_goal),
            )
            for row in goals.itertuples(index=False)
        ]
    freshness = None if matches.empty else matches.fetched_at.max()
    return TournamentResponse(
        competition=competition, name=name, season=season,
        stages=stages, matches=payload, scorers=scorers,
        source=_source("openfootball", "tournament", freshness),
    )


def list_players(
    store: ReadOnlyStore,
    query: str | None = None,
    team: str | None = None,
    position: str | None = None,
    sort_by: str | None = None,
    cursor: str | None = None,
    limit: int = 50,
) -> PlayerListResponse:
    limit = max(1, min(int(limit), 200))
    if not _has(store, "open_players"):
        return PlayerListResponse(
            players=[], page=PageMeta(next_cursor=None, limit=limit, returned=0),
            source=_source("transfermarkt-open", "empty"),
        )
    frame = store.query(
        "SELECT source, player_id, team, player, position, nationality, date_born, "
        "data_as_of, image_url, market_value_eur FROM open_players"
    )
    media = _team_media_map(store)
    facet_names = sorted(frame.team.dropna().unique(), key=lambda value: (display_team(value) or value).casefold())
    team_facets = [_build_team_ref(name, media) for name in facet_names]
    if team:
        key = team_key(team) or team
        frame = frame[(frame.team.map(team_key) == key) | (frame.team == team)]
    positions = sorted(value for value in frame.position.dropna().unique() if value)
    if position:
        frame = frame[frame.position == position]
    if query:
        search_columns = ("player", "team", "position", "nationality")
        frame = frame.copy()
        frame["_search_score"] = frame.apply(
            lambda row: max(_fuzzy_score(query, row[column]) for column in search_columns),
            axis=1,
        )
        frame = frame[frame._search_score >= 0.58]
    if sort_by == "market_value":
        frame = frame[frame.market_value_eur.notna()].sort_values(
            ["market_value_eur", "player"], ascending=[False, True]
        )
    else:
        frame = frame.sort_values(["player", "player_id"])
    total_count = len(frame)
    average_age = None
    valid_births = pd.to_datetime(frame.date_born, errors="coerce")
    valid_snapshots = pd.to_datetime(frame.data_as_of, errors="coerce")
    age_days = (valid_snapshots - valid_births).dt.days
    if age_days.notna().any():
        average_age = round(float((age_days / 365.2425).mean()), 1)
    nationality_count = int(frame.nationality.replace("", pd.NA).nunique())
    total_market_value = int(pd.to_numeric(frame.market_value_eur, errors="coerce").fillna(0).sum())
    token = decode_cursor(cursor)
    if token:
        frame = frame[
            (frame.player > token["n"])
            | ((frame.player == token["n"]) & (frame.player_id > token["id"]))
        ]
    page = frame.head(limit + 1)
    has_more = len(page) > limit
    page = page.head(limit)
    next_cursor = None
    if has_more and not page.empty:
        last = page.iloc[-1]
        next_cursor = encode_cursor({"n": last.player, "id": last.player_id})
    players = [
        PlayerSummary(
            player_id=str(row.player_id), name=row.player, team=_build_team_ref(row.team, media),
            position=row.position, nationality=row.nationality,
            image_url=None if pd.isna(getattr(row, "image_url", None)) else row.image_url,
            market_value_eur=None if pd.isna(getattr(row, "market_value_eur", None)) else int(row.market_value_eur),
            source=row.source,
        )
        for row in page.itertuples(index=False)
    ]
    return PlayerListResponse(
        players=players,
        page=PageMeta(next_cursor=next_cursor, limit=limit, returned=len(players)),
        total_count=total_count,
        teams=team_facets,
        positions=positions,
        average_age=average_age,
        nationality_count=nationality_count,
        total_market_value_eur=total_market_value,
        source=_source("transfermarkt-open", "players"),
    )


def get_player(store: ReadOnlyStore, player_id: str) -> PlayerProfileResponse | None:
    if not _has(store, "open_players"):
        return None
    frame = store.query("SELECT * FROM open_players WHERE player_id = ?", [player_id])
    if frame.empty:
        return None
    row = frame.iloc[0]
    stats: list[PlayerStat] = []
    if _has(store, "open_player_stats"):
        stat_frame = store.query(
            "SELECT * FROM open_player_stats WHERE player_id = ? ORDER BY season DESC, competition",
            [player_id],
        )
        for item in stat_frame.itertuples(index=False):
            stats.append(PlayerStat(
                season=int(item.season), competition=item.competition, statistic="season",
                appearances=int(item.appearances), goals=int(item.goals), assists=int(item.assists),
                minutes_played=int(item.minutes_played), yellow_cards=int(item.yellow_cards),
                red_cards=int(item.red_cards),
            ))
    tm_map = _team_media_map(store)
    image = None if pd.isna(row.image_url) else row.image_url
    return PlayerProfileResponse(
        player_id=str(row.player_id), name=row.player, team=_build_team_ref(row.team, tm_map),
        position=None if pd.isna(row.position) else row.position,
        sub_position=None if pd.isna(row.sub_position) else row.sub_position,
        nationality=None if pd.isna(row.nationality) else row.nationality,
        date_born=_as_date(row.date_born),
        height_cm=None if pd.isna(row.height_cm) else int(row.height_cm),
        foot=None if pd.isna(row.foot) else row.foot,
        market_value_eur=None if pd.isna(row.market_value_eur) else int(row.market_value_eur),
        image_url=image, source=row.source, stats=stats,
        coverage=_source(row.source, "player-profile", row.fetched_at),
    )


def _calibration(validation: pd.DataFrame) -> list[CalibrationBin]:
    if validation.empty or "actual_result" not in validation:
        return []
    bins = []
    for column, outcome in (
        ("home_probability", "Home"),
        ("draw_probability", "Draw"),
        ("away_probability", "Away"),
    ):
        observed = (validation.actual_result == outcome).astype(float)
        bins.append(CalibrationBin(
            predicted_outcome=outcome,
            mean_probability=float(validation[column].mean()),
            observed_rate=float(observed.mean()),
            samples=int(len(validation)),
        ))
    return bins


def _league_title_outlooks(store: ReadOnlyStore, tm_map: dict[str, Any]) -> list[LeagueTitleOutlook]:
    """Project title shares from current points with conservative early-season smoothing."""
    live = current_season()
    grouped: dict[str, list[Team]] = {}
    for team in list_teams(store, None, live).teams:
        if team.competition in RECENT_LEAGUES:
            grouped.setdefault(team.competition, []).append(team)

    outlooks: list[LeagueTitleOutlook] = []
    for competition, teams in grouped.items():
        if len(teams) < 2:
            continue
        ranked = sorted(teams, key=lambda item: (-item.points, -item.played, item.name))
        season_matches = 2 * (len(teams) - 1)
        projections = []
        for rank, team in enumerate(ranked, 1):
            remaining = max(0, season_matches - team.played)
            smoothed_ppg = (team.points + 5 * 1.35) / (team.played + 5)
            projections.append((rank, team, team.points + remaining * smoothed_ppg, remaining))
        best = max(row[2] for row in projections)
        uncertainty = max(2.5, 1.6 * np.sqrt(max(row[3] for row in projections)))
        weights = np.exp(np.array([(row[2] - best) / uncertainty for row in projections]))
        weights /= weights.sum()
        for (rank, team, projected, _), probability in zip(projections, weights):
            outlooks.append(LeagueTitleOutlook(
                competition=competition,
                season=live,
                team=_build_team_ref(team.name, tm_map),
                current_rank=rank,
                played=team.played,
                points=team.points,
                projected_points=round(float(projected), 1),
                title_probability=round(float(probability), 4),
            ))
    return outlooks


def predictions(store: ReadOnlyStore) -> PredictionsResponse:
    empty = PredictionsResponse(source=_source("softmax-form-elo", "empty"))
    if not _has(store, "prediction_models"):
        return empty
    models = store.query("SELECT * FROM prediction_models ORDER BY trained_at DESC LIMIT 1")
    if models.empty:
        return empty
    model = models.iloc[0]
    metrics = json.loads(model.metrics) if isinstance(model.metrics, str) else (model.metrics or {})
    forecasts = []
    calibration: list[CalibrationBin] = []
    tm_map = _team_media_map(store)
    if _has(store, "match_predictions"):
        rows = store.query(
            "SELECT * FROM match_predictions WHERE model_id = ?", [model.model_id]
        )
        future = rows[rows.prediction_kind == "forecast"] if not rows.empty else rows
        for row in future.itertuples(index=False):
            forecasts.append(Forecast(
                competition=row.league, season=int(row.season),
                match_date=_as_date(row.match_date) or date.min,
                home=_build_team_ref(row.home_team, tm_map), away=_build_team_ref(row.away_team, tm_map),
                predicted_result=row.predicted_result,
                home_probability=float(row.home_probability),
                draw_probability=float(row.draw_probability),
                away_probability=float(row.away_probability),
            ))
        validation = rows[rows.prediction_kind == "validation"] if not rows.empty else rows
        calibration = _calibration(validation)
    return PredictionsResponse(
        model_id=model.model_id, model_name=model.model_name,
        trained_at=_as_datetime(model.trained_at),
        validation_cutoff=_as_date(model.validation_cutoff),
        metrics=metrics, calibration=calibration, forecasts=forecasts,
        league_outlooks=_league_title_outlooks(store, tm_map),
        source=_source("softmax-form-elo", "predictions", model.trained_at),
    )


def overview(
    store: ReadOnlyStore,
    team: str | None = None,
    competition: str | None = None,
    season: int | None = None,
) -> OverviewResponse:
    if season is None:
        season = current_season()
    if not competition:
        competition = "E0"

    tm_map = _team_media_map(store)
    comp_years = set(seasons() + ([current_season()] if current_season() not in seasons() else []))
    if _has(store, "tournament_matches") and competition in TOURNAMENTS:
        try:
            t_years = store.query("SELECT DISTINCT season FROM tournament_matches WHERE competition = ?", [competition])["season"].tolist()
            comp_years.update(t_years)
        except Exception:
            pass
    all_years = sorted(list(comp_years))

    # Fetch ranking rows for ALL teams in this competition across all seasons
    analysis_filters = AnalysisFilters(
        competitions=[competition],
        seasons=all_years,
        teams=[],
    )
    analysis_data = build_analysis(store, analysis_filters)

    # Determine spotlight team (ensure it belongs to competition)
    comp_clubs = [r.team.name for r in analysis_data.rankings if r.competition == competition]
    comp_keys = {team_key(t): t for t in comp_clubs}

    focus_team = None
    if team:
        tkey = team_key(team) or team
        if tkey in comp_keys:
            focus_team = comp_keys[tkey]
        elif team in comp_clubs:
            focus_team = team

    if not focus_team:
        season_rankings = [r for r in analysis_data.rankings if r.competition == competition and r.season == season]
        if season_rankings:
            season_rankings.sort(key=lambda r: (r.rank, -r.points))
            focus_team = season_rankings[0].team.name
        elif comp_clubs:
            focus_team = comp_clubs[0]
        else:
            focus_team = "Arsenal"

    # Find ranking stats for the spotlight team in the selected season
    spotlight_stats = None
    for r in analysis_data.rankings:
        if (team_key(r.team.name) == team_key(focus_team) or r.team.name == focus_team) and r.season == season:
            spotlight_stats = r
            break

    # Find latest 2 completed matches for spotlight team
    spotlight_key = team_key(focus_team) or focus_team
    completed = []
    q = """
    SELECT league AS competition, season, match_date, home_team, away_team, home_goals, away_goals, referee, source
    FROM (
        SELECT league, season, match_date, home_team, away_team, home_goals, away_goals, referee, source FROM recent_matches WHERE home_goals IS NOT NULL
        UNION ALL
        SELECT league, season, match_date, home_team, away_team, home_goals, away_goals, referee, 'football-data.co.uk' AS source FROM matches WHERE home_goals IS NOT NULL
    )
    ORDER BY match_date DESC
    """
    df = store.query(q)
    filtered = df[(df.home_team.map(team_key) == spotlight_key) | (df.away_team.map(team_key) == spotlight_key)]
    for row in filtered.head(2).itertuples(index=False):
        completed.append(_match_from_row(row, "competition", tm_map))
    latest_match = completed[0] if len(completed) > 0 else None
    previous_match = completed[1] if len(completed) > 1 else None

    # Next listed fixture from the current event feed, independent of model coverage.
    next_match = None
    if season == current_season() and _has(store, "recent_events"):
        upcoming = store.query(
            "SELECT * FROM recent_events WHERE season = ? AND event_kind = 'next' ORDER BY match_date, event_id",
            [season],
        )
        if not upcoming.empty:
            upcoming = upcoming[
                (upcoming.home_team.map(team_key) == spotlight_key)
                | (upcoming.away_team.map(team_key) == spotlight_key)
            ]
            if not upcoming.empty:
                next_match = _match_from_row(upcoming.iloc[0], "league", tm_map)

    # Probability forecast remains optional and never hides a listed fixture.
    preds = predictions(store)
    next_fixture = None
    for f in preds.forecasts:
        if (team_key(f.home.name) == spotlight_key or team_key(f.away.name) == spotlight_key
            or f.home.name == focus_team or f.away.name == focus_team):
            next_fixture = f
            break

    spotlight = ClubSpotlight(
        team=_build_team_ref(focus_team, tm_map),
        league=competition,
        season=season,
        played=spotlight_stats.played if spotlight_stats else 0,
        wins=spotlight_stats.wins if spotlight_stats else 0,
        draws=spotlight_stats.draws if spotlight_stats else 0,
        losses=spotlight_stats.losses if spotlight_stats else 0,
        points=spotlight_stats.points if spotlight_stats else 0,
        points_per_game=spotlight_stats.points_per_game if spotlight_stats else 0.0,
        goal_difference=spotlight_stats.goal_difference if spotlight_stats else 0,
        latest_match=latest_match,
        previous_match=previous_match,
        next_match=next_match,
        next_fixture=next_fixture,
    )

    return OverviewResponse(
        spotlight=spotlight,
        performance_over_time=analysis_data.rankings,
        elo_trajectory=analysis_data.elo_ratings,
        forecasts=preds.forecasts,
        source=_source("duckdb", "overview"),
    )


def list_transfers(
    store: ReadOnlyStore,
    season: int | None = None,
    competition: str | None = None,
    club: str | None = None,
    query: str | None = None,
    cursor: str | None = None,
    limit: int = 50,
) -> TransferListResponse:
    limit = max(1, min(int(limit), 200))
    if not _has(store, "transfers"):
        return TransferListResponse(
            transfers=[], total_count=0,
            page=PageMeta(next_cursor=None, limit=limit, returned=0),
            source=_source("transfermarkt-open", "empty"),
        )

    sql = "SELECT * FROM transfers WHERE 1=1"
    params = []
    if season is not None:
        try:
            season_int = int(season)
            sql += " AND season = ?"
            params.append(season_int)
        except (ValueError, TypeError):
            pass  # season was 'all' or non-integer
    if competition and str(competition).lower() not in ("all", "any", "none", ""):
        sql += " AND (from_competition = ? OR to_competition = ?)"
        params.extend([competition, competition])
    elif not competition or str(competition).lower() in ("all", ""):
        # Showcase top transfers involving Big 5 European leagues
        sql += " AND (from_competition IN ('E0', 'SP1', 'D1', 'I1', 'F1') OR to_competition IN ('E0', 'SP1', 'D1', 'I1', 'F1'))"
    if club:
        sql += " AND (from_club_name ILIKE ? OR to_club_name ILIKE ?)"
        params.extend([f"%{club}%", f"%{club}%"])
    if query:
        sql += " AND (player_name ILIKE ? OR from_club_name ILIKE ? OR to_club_name ILIKE ?)"
        params.extend([f"%{query}%", f"%{query}%", f"%{query}%"])

    sql += " ORDER BY market_value_eur DESC NULLS LAST, transfer_fee DESC NULLS LAST, transfer_date DESC NULLS LAST"
    frame = store.query(sql, params)
    total_count = len(frame)

    page = frame.head(limit)
    tm_map = _team_media_map(store)
    rows = []
    for r in page.itertuples(index=False):
        rows.append(TransferRow(
            transfer_id=str(r.transfer_id),
            player_id=str(r.player_id),
            player_name=r.player_name,
            transfer_date=_as_date(r.transfer_date),
            transfer_season=r.transfer_season,
            season=int(r.season),
            from_club=_build_team_ref(r.from_club_name, tm_map),
            to_club=_build_team_ref(r.to_club_name, tm_map),
            transfer_fee=None if pd.isna(r.transfer_fee) else float(r.transfer_fee),
            market_value_eur=None if pd.isna(r.market_value_eur) else int(r.market_value_eur),
            from_competition=None if pd.isna(r.from_competition) else r.from_competition,
            to_competition=None if pd.isna(r.to_competition) else r.to_competition,
            image_url=None if pd.isna(r.image_url) else r.image_url,
        ))

    return TransferListResponse(
        transfers=rows,
        total_count=total_count,
        page=PageMeta(next_cursor=None, limit=limit, returned=len(rows)),
        source=_source("transfermarkt-open", "transfers"),
    )


def quality(store: ReadOnlyStore) -> QualityResponse:
    def row_count(table: str) -> int:
        return int(store.scalar(f"SELECT count(*) FROM {table}") or 0) if _has(store, table) else 0

    completed = seasons()
    live = current_season()
    match_count = row_count("matches")
    recent_count = row_count("recent_matches")
    fixtures = pd.DataFrame()
    if _has(store, "matches"):
        fixtures = store.query("SELECT league, season, home_shots, away_shots, home_sot, away_sot, home_corners FROM matches")
    if _has(store, "recent_matches"):
        recent = store.query("SELECT league, season, home_shots, away_shots, home_sot, away_sot, home_corners FROM recent_matches")
        fixtures = pd.concat([fixtures, recent], ignore_index=True) if not recent.empty else fixtures
    impossible = 0
    null_coverage: dict[str, float] = {}
    if not fixtures.empty:
        impossible = int((
            (fixtures.home_sot > fixtures.home_shots) | (fixtures.away_sot > fixtures.away_shots)
        ).fillna(False).sum())
        for column in ("home_shots", "away_shots", "home_sot", "away_sot"):
            null_coverage[column] = float(fixtures[column].isna().mean())
    covered = set()
    live_leagues = set()
    if not fixtures.empty:
        covered = set(zip(fixtures.league, fixtures.season.astype(int)))
        live_leagues = set(fixtures.loc[fixtures.season == live, "league"])
    expected_completed = len(LEAGUES) * len(completed)
    complete_cells = len([1 for league in LEAGUES for year in completed if (league, year) in covered])
    coverage_counts = fixtures.groupby(["league", "season"]).size().to_dict() if not fixtures.empty else {}
    grid = []
    for league in list(LEAGUES) + [code for code in RECENT_LEAGUES if code not in LEAGUES]:
        for year in completed + ([live] if live not in completed else []):
            if (league, year) in covered:
                status = "live_partial" if year == live else "complete"
            else:
                status = "missing"
            grid.append(QualityCell(
                competition=league,
                season=year,
                status=status,
                match_count=int(coverage_counts.get((league, year), 0)),
            ))
    checksums = []
    if _has(store, "ingestion_runs"):
        runs = store.query(
            "SELECT league, season, sha256, status, fetched_at, row_count FROM ingestion_runs "
            "ORDER BY fetched_at DESC LIMIT 25"
        )
        checksums = runs.replace({np.nan: None}).to_dict("records")
    stamps: dict[str, datetime | str | None] = {}
    if _has(store, "analytics_metadata"):
        stamps["analytics"] = _as_datetime(store.scalar("SELECT max(refreshed_at) FROM analytics_metadata"))
    if _has(store, "ingestion_runs"):
        stamps["ingestion"] = _as_datetime(store.scalar("SELECT max(fetched_at) FROM ingestion_runs"))
    if _has(store, "open_players"):
        stamps["players"] = _as_datetime(store.scalar("SELECT max(fetched_at) FROM open_players"))
    if _has(store, "match_contexts"):
        stamps["match_contexts"] = _as_datetime(store.scalar("SELECT max(fetched_at) FROM match_contexts"))
    if _has(store, "reference_standings"):
        stamps["reference"] = _as_datetime(store.scalar("SELECT max(fetched_at) FROM reference_standings"))
    if _has(store, "recent_matches"):
        stamps["recent"] = _as_datetime(store.scalar("SELECT max(fetched_at) FROM recent_matches"))
    if _has(store, "team_media"):
        stamps["media"] = _as_datetime(store.scalar("SELECT max(fetched_at) FROM team_media"))
    if _has(store, "tournament_matches"):
        stamps["tournaments"] = _as_datetime(store.scalar("SELECT max(fetched_at) FROM tournament_matches"))
    if _has(store, "event_statistics"):
        stamps["event_details"] = _as_datetime(store.scalar("SELECT max(fetched_at) FROM event_statistics"))
    if _has(store, "prediction_models"):
        stamps["predictions"] = _as_datetime(store.scalar("SELECT max(trained_at) FROM prediction_models"))

    reference_rows = row_count("reference_standings")
    tracked_players = row_count("open_players")
    player_stat_rows = row_count("open_player_stats")
    artwork_rows = row_count("team_media") + row_count("competition_media")
    tournament_match_count = row_count("tournament_matches")
    tournament_goal_count = row_count("tournament_goals")
    event_stat_count = row_count("event_statistics")
    timeline_count = row_count("event_timeline")
    lineup_count = row_count("event_lineups")
    prediction_count = row_count("match_predictions")
    recent_competitions = int(fixtures.loc[fixtures.season == live, "league"].nunique()) if not fixtures.empty else 0
    player_clubs = int(store.scalar("SELECT count(DISTINCT team) FROM open_players") or 0) if _has(store, "open_players") else 0
    tournament_teams = 0
    tournament_breakdown: dict[str, int] = {}
    if _has(store, "tournament_matches"):
        tournament_teams = int(store.scalar(
            "SELECT count(DISTINCT team) FROM (SELECT home_team AS team FROM tournament_matches UNION SELECT away_team FROM tournament_matches)"
        ) or 0)
        breakdown = store.query("SELECT competition, count(*) AS matches FROM tournament_matches GROUP BY competition")
        tournament_breakdown = {str(row.competition): int(row.matches) for row in breakdown.itertuples(index=False)}
    context_rich = int(fixtures.home_corners.notna().sum()) if not fixtures.empty and "home_corners" in fixtures else 0
    match_context_rows = row_count("match_contexts")
    formation_rows = int(store.scalar(
        "SELECT count(*) FROM match_contexts WHERE home_formation <> '' OR away_formation <> ''"
    ) or 0) if _has(store, "match_contexts") else 0
    coach_rows = int(store.scalar(
        "SELECT count(*) FROM match_contexts WHERE home_coach <> '' OR away_coach <> ''"
    ) or 0) if _has(store, "match_contexts") else 0
    shots = shot_analysis(store)
    caps = [
        "TheSportsDB free standings and player feeds are explicitly capped.",
        "Transfermarkt Open Dataset is a 2025/26 snapshot with no 2026/27 squad rows.",
        "Current-season fixtures are labelled live partial and never treated as complete.",
    ]
    return QualityResponse(
        completed_coverage=f"{complete_cells}/{expected_completed}",
        live_competitions=f"{len(live_leagues)}/{len(RECENT_LEAGUES)}",
        match_records=match_count + recent_count,
        impossible_shot_rows=impossible,
        reference_rows=reference_rows,
        recent_competitions=recent_competitions,
        completed_results=recent_count,
        tracked_players=tracked_players,
        player_clubs=player_clubs,
        player_stat_rows=player_stat_rows,
        artwork_rows=artwork_rows,
        tournament_matches=tournament_match_count,
        tournament_teams=tournament_teams,
        tournament_breakdown=tournament_breakdown,
        context_rich_matches=context_rich,
        match_context_rows=match_context_rows,
        formation_rows=formation_rows,
        coach_rows=coach_rows,
        tournament_goals=tournament_goal_count,
        detailed_event_stats=event_stat_count,
        timeline_events=timeline_count,
        lineup_rows=lineup_count,
        model_predictions=prediction_count,
        source_caps=caps,
        null_coverage=null_coverage,
        checksums=checksums,
        refresh_timestamps=stamps,
        grid=grid,
        shot_coverage=shots.coverage,
        source=_source("duckdb", "quality"),
    )
