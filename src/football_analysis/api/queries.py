"""DuckDB reads that power the versioned API without Streamlit."""

from __future__ import annotations

import hashlib
import json
from datetime import date, datetime

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
    Forecast,
    FormRow,
    HealthResponse,
    Match,
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
    RefereeSummary,
    SeasonCoverage,
    SourceMeta,
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
    COMPETITIONS,
    LEAGUES,
    RECENT_LEAGUES,
    TOURNAMENTS,
    current_season,
    label,
    seasons,
)
from football_analysis.teams import display_team, team_key


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


def _has(store: ReadOnlyStore, name: str) -> bool:
    return name in store.tables()


def _source(name: str, coverage: str, freshness=None) -> SourceMeta:
    return SourceMeta(source=name, coverage=coverage, freshness=_as_datetime(freshness) or freshness)


def snapshot_etag(store: ReadOnlyStore) -> str:
    parts: list[str] = []
    tables = store.tables()
    for table, column in (
        ("ingestion_runs", "fetched_at"),
        ("recent_matches", "fetched_at"),
        ("tournament_matches", "fetched_at"),
        ("analytics_metadata", "refreshed_at"),
        ("prediction_models", "trained_at"),
        ("open_players", "fetched_at"),
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
                label=str(year) if code == "WC" else label(int(year)),
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
    if not _has(store, "team_seasons"):
        return TeamListResponse(teams=[], source=_source("duckdb", "empty"))
    sql = "SELECT league, season, team, played, points FROM team_seasons WHERE 1=1"
    params: list = []
    if competition:
        sql += " AND league = ?"
        params.append(competition)
    if season is not None:
        sql += " AND season = ?"
        params.append(season)
    sql += " ORDER BY league, season, team"
    frame = store.query(sql, params)
    if competition in TOURNAMENTS and _has(store, "tournament_matches"):
        tourney = store.query(
            "SELECT competition AS league, season, home_team AS team FROM tournament_matches "
            "UNION ALL SELECT competition, season, away_team FROM tournament_matches"
        )
        if competition:
            tourney = tourney[tourney.league == competition]
        if season is not None:
            tourney = tourney[tourney.season == season]
        if not tourney.empty:
            extra = tourney.drop_duplicates().assign(played=0, points=0)
            frame = pd.concat([frame, extra], ignore_index=True).drop_duplicates(
                ["league", "season", "team"], keep="first",
            )
    tm_map = _team_media_map(store)
    teams = [
        Team(
            team_id=canonical_team_id(row.team),
            name=display_team(row.team),
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
            "home_goals, away_goals, referee, CAST(NULL AS VARCHAR) AS stage, "
            "CAST(NULL AS VARCHAR) AS venue, 'football-data.co.uk' AS source FROM matches"
        ))
    if _has(store, "recent_matches"):
        frames.append(store.query(
            "SELECT league AS competition, season, match_date, home_team, away_team, "
            "home_goals, away_goals, referee, CAST(NULL AS VARCHAR) AS stage, "
            "CAST(NULL AS VARCHAR) AS venue, source FROM recent_matches"
        ))
    if _has(store, "tournament_matches"):
        frames.append(store.query(
            "SELECT competition, season, match_date, home_team, away_team, "
            "home_goals, away_goals, CAST(NULL AS VARCHAR) AS referee, stage, venue, source "
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
        ["match_date", "competition", "home_team", "away_team"]
    ).reset_index(drop=True)
    token = decode_cursor(cursor)
    if token:
        cursor_date = pd.Timestamp(token["d"])
        mask = (
            (frame.match_date > cursor_date)
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
    if sort_by == "market_value":
        frame = store.query(
            "SELECT source, player_id, team, player, position, nationality, image_url, market_value_eur "
            "FROM open_players WHERE market_value_eur IS NOT NULL ORDER BY market_value_eur DESC, player"
        )
    else:
        frame = store.query(
            "SELECT source, player_id, team, player, position, nationality, image_url, market_value_eur "
            "FROM open_players ORDER BY player, player_id"
        )
    if team:
        key = team_key(team) or team
        frame = frame[(frame.team.map(team_key) == key) | (frame.team == team)]
    if query:
        needle = query.casefold()
        frame = frame[frame.player.str.casefold().str.contains(needle, regex=False, na=False)]
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
    tm_map = _team_media_map(store)
    players = [
        PlayerSummary(
            player_id=str(row.player_id), name=row.player, team=_build_team_ref(row.team, tm_map),
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
    all_years = seasons() + ([current_season()] if current_season() not in seasons() else [])

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

    # Next fixture from predictions
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
        sql += " AND season = ?"
        params.append(season)
    if competition:
        sql += " AND (from_competition = ? OR to_competition = ?)"
        params.extend([competition, competition])
    if club:
        sql += " AND (from_club_name ILIKE ? OR to_club_name ILIKE ?)"
        params.extend([f"%{club}%", f"%{club}%"])
    if query:
        sql += " AND (player_name ILIKE ? OR from_club_name ILIKE ? OR to_club_name ILIKE ?)"
        params.extend([f"%{query}%", f"%{query}%", f"%{query}%"])

    sql += " ORDER BY transfer_date DESC NULLS LAST, market_value_eur DESC NULLS LAST, transfer_fee DESC NULLS LAST"
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
    completed = seasons()
    live = current_season()
    match_count = int(store.scalar("SELECT count(*) FROM matches") or 0) if _has(store, "matches") else 0
    recent_count = int(store.scalar("SELECT count(*) FROM recent_matches") or 0) if _has(store, "recent_matches") else 0
    fixtures = pd.DataFrame()
    if _has(store, "matches"):
        fixtures = store.query("SELECT league, season, home_shots, away_shots, home_sot, away_sot FROM matches")
    if _has(store, "recent_matches"):
        recent = store.query("SELECT league, season, home_shots, away_shots, home_sot, away_sot FROM recent_matches")
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
    grid = []
    for league in list(LEAGUES) + [code for code in RECENT_LEAGUES if code not in LEAGUES]:
        for year in completed + ([live] if live not in completed else []):
            if (league, year) in covered:
                status = "live_partial" if year == live else "complete"
            else:
                status = "missing"
            grid.append(QualityCell(competition=league, season=year, status=status, match_count=0))
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
        source_caps=caps,
        null_coverage=null_coverage,
        checksums=checksums,
        refresh_timestamps=stamps,
        grid=grid,
        source=_source("duckdb", "quality"),
    )
