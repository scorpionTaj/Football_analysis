"""Matches, shots, event details and the Match Centre."""

from __future__ import annotations

from datetime import date
from typing import Any

import numpy as np
import pandas as pd

from football_analysis.api.contracts import (
    EventDetailResponse,
    EventLineupItem,
    EventListResponse,
    EventStatistic,
    EventSummary,
    EventTimelineItem,
    Match,
    MatchCentreDetailResponse,
    MatchListResponse,
    PageMeta,
    ShotAnalysisResponse,
    ShotCoverageRow,
    ShotEfficiencyRow,
)
from football_analysis.api.db import ReadOnlyStore
from football_analysis.api.pagination import decode_cursor, encode_cursor
from football_analysis.config import (
    TOURNAMENTS,
)
from football_analysis.teams import display_team, team_key
from football_analysis.api.queries._shared import (
    _as_date,
    _build_team_ref,
    _fuzzy_score,
    _has,
    _match_from_row,
    _present,
    _search_text,
    _source,
    _team_media_map,
)


def list_matches(
    store: ReadOnlyStore,
    competition: str | None = None,
    season: int | None = None,
    team: str | None = None,
    opponent: str | None = None,
    venue: str | None = None,
    cursor: str | None = None,
    limit: int = 50,
    query: str | None = None,
    source_name: str = "duckdb",
) -> MatchListResponse:
    limit = max(1, min(int(limit), 200))
    frame = load_match_source_rows(store)
    if frame.empty:
        return MatchListResponse(
            matches=[], page=PageMeta(next_cursor=None, limit=limit, returned=0),
            source=_source(source_name, "empty"),
        )
    frame["home_key"] = frame.home_team.map(team_key)
    frame["away_key"] = frame.away_team.map(team_key)
    frame["has_result"] = frame.home_goals.notna().astype(int)
    completed_pairs = set(zip(
        frame.loc[frame.has_result == 1, "competition"],
        frame.loc[frame.has_result == 1, "season"],
        frame.loc[frame.has_result == 1, "home_key"],
        frame.loc[frame.has_result == 1, "away_key"],
    ))
    visible = pd.Series([
        bool(row.has_result) or (row.competition, row.season, row.home_key, row.away_key) not in completed_pairs
        for row in frame.itertuples(index=False)
    ], index=frame.index, dtype=bool)
    frame = frame[visible]
    frame = frame.sort_values("has_result", ascending=False).drop_duplicates(
        ["competition", "season", "home_key", "away_key", "match_date"], keep="first",
    ).drop(columns=["home_key", "away_key", "has_result"])
    frame["match_date"] = pd.to_datetime(frame.match_date)
    if competition:
        frame = frame[frame.competition == competition]
    if season is not None:
        frame = frame[frame.season == season]
    if team:
        key = team_key(team) or team
        home_keys = frame.home_team.map(team_key)
        away_keys = frame.away_team.map(team_key)
        team_mask = (home_keys == key) | (away_keys == key) | (frame.home_team == team) | (frame.away_team == team)
        if opponent:
            opponent_key = team_key(opponent) or opponent
            opponent_mask = (
                (home_keys == opponent_key) | (away_keys == opponent_key)
                | (frame.home_team == opponent) | (frame.away_team == opponent)
            )
            team_mask &= opponent_mask
        if venue == "Home":
            team_mask &= home_keys == key
        elif venue == "Away":
            team_mask &= away_keys == key
        frame = frame[team_mask]
    elif venue:
        frame = frame[frame.venue == venue]
    if query and _search_text(query):
        search_columns = ("home_team", "away_team", "referee", "competition", "stage", "venue")
        matched = frame.apply(
            lambda row: any(_fuzzy_score(query, value) >= 0.75 for value in (
                *(row[column] for column in search_columns),
                display_team(row.home_team), display_team(row.away_team),
            )),
            axis=1,
        )
        frame = frame[matched]
    if frame.empty:
        return MatchListResponse(
            matches=[], page=PageMeta(next_cursor=None, limit=limit, returned=0),
            source=_source(source_name, "matches"),
        )
    frame["sort_group"] = frame.home_goals.isna().astype(int)
    ordinal = frame.match_date.map(lambda value: value.date().toordinal())
    frame["sort_order"] = np.where(frame.sort_group == 1, -ordinal, ordinal)
    frame = frame.sort_values(
        ["sort_group", "sort_order", "competition", "home_team", "away_team"],
        ascending=[False, False, True, True, True],
    ).reset_index(drop=True)
    token = decode_cursor(cursor, required=("c", "h", "a"))
    if token and "o" not in token and "d" not in token:
        raise ValueError("Invalid cursor")
    if token:
        cursor_group = int(token.get("g", 0))
        cursor_order = int(token["o"]) if "o" in token else pd.Timestamp(token["d"]).date().toordinal()
        mask = (
            (frame.sort_group < cursor_group)
            | ((frame.sort_group == cursor_group) & (frame.sort_order < cursor_order))
            | ((frame.sort_group == cursor_group) & (frame.sort_order == cursor_order) & (frame.competition > token["c"]))
            | (
                (frame.sort_group == cursor_group)
                & (frame.sort_order == cursor_order)
                & (frame.competition == token["c"])
                & (frame.home_team > token["h"])
            )
            | (
                (frame.sort_group == cursor_group)
                & (frame.sort_order == cursor_order)
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
            "g": int(last.sort_group),
            "o": int(last.sort_order),
            "c": last.competition,
            "h": last.home_team,
            "a": last.away_team,
        })
    tm_map = _team_media_map(store)
    matches = [_match_from_row(row, "competition", tm_map) for row in page.itertuples(index=False)]
    return MatchListResponse(
        matches=matches,
        page=PageMeta(next_cursor=next_cursor, limit=limit, returned=len(matches)),
        source=_source(source_name, "matches"),
    )


def load_match_source_rows(store: ReadOnlyStore) -> pd.DataFrame:
    """Load the four source feeds before shared match reconciliation and filtering."""
    frames = []
    if _has(store, "mart_dashboard_match"):
        frames.append(store.query(
            "SELECT league AS competition, season, match_date, home_team, away_team, "
            "home_goals, away_goals, home_shots, away_shots, home_sot, away_sot, "
            "half_time_home_goals, half_time_away_goals, home_corners, away_corners, "
            "home_fouls, away_fouls, home_yellows, away_yellows, home_reds, away_reds, "
            "referee, CAST(NULL AS VARCHAR) AS kickoff_time, CAST(NULL AS VARCHAR) AS stage, "
            "CAST(NULL AS VARCHAR) AS venue, 'football-data.co.uk' AS source FROM mart_dashboard_match "
            "ORDER BY league, season, match_date, home_team, away_team"
        ))
    if _has(store, "recent_matches"):
        frames.append(store.query(
            "SELECT league AS competition, season, match_date, home_team, away_team, "
            "home_goals, away_goals, home_shots, away_shots, home_sot, away_sot, "
            "half_time_home_goals, half_time_away_goals, home_corners, away_corners, "
            "home_fouls, away_fouls, home_yellows, away_yellows, home_reds, away_reds, "
            "referee, CAST(NULL AS VARCHAR) AS kickoff_time, CAST(NULL AS VARCHAR) AS stage, "
            "CAST(NULL AS VARCHAR) AS venue, source FROM recent_matches "
            "ORDER BY league, season, match_date, home_team, away_team"
        ))
    if _has(store, "fct_tournament_match"):
        frames.append(store.query(
            "SELECT competition, season, match_date, home_team, away_team, "
            "home_goals, away_goals, CAST(NULL AS INTEGER) AS home_shots, "
            "CAST(NULL AS INTEGER) AS away_shots, CAST(NULL AS INTEGER) AS home_sot, "
            "CAST(NULL AS INTEGER) AS away_sot, CAST(NULL AS INTEGER) AS half_time_home_goals, "
            "CAST(NULL AS INTEGER) AS half_time_away_goals, CAST(NULL AS INTEGER) AS home_corners, "
            "CAST(NULL AS INTEGER) AS away_corners, CAST(NULL AS INTEGER) AS home_fouls, "
            "CAST(NULL AS INTEGER) AS away_fouls, CAST(NULL AS INTEGER) AS home_yellows, "
            "CAST(NULL AS INTEGER) AS away_yellows, CAST(NULL AS INTEGER) AS home_reds, "
            "CAST(NULL AS INTEGER) AS away_reds, CAST(NULL AS VARCHAR) AS referee, "
            "CAST(NULL AS VARCHAR) AS kickoff_time, stage, venue, source "
            "FROM fct_tournament_match "
            "ORDER BY competition, season, match_date, home_team, away_team"
        ))
    if _has(store, "recent_events"):
        events = store.query(
            "SELECT league AS competition, season, match_date, home_team, away_team, "
            "CAST(NULL AS INTEGER) AS home_goals, CAST(NULL AS INTEGER) AS away_goals, "
            "CAST(NULL AS INTEGER) AS home_shots, CAST(NULL AS INTEGER) AS away_shots, "
            "CAST(NULL AS INTEGER) AS home_sot, CAST(NULL AS INTEGER) AS away_sot, "
            "CAST(NULL AS INTEGER) AS half_time_home_goals, CAST(NULL AS INTEGER) AS half_time_away_goals, "
            "CAST(NULL AS INTEGER) AS home_corners, CAST(NULL AS INTEGER) AS away_corners, "
            "CAST(NULL AS INTEGER) AS home_fouls, CAST(NULL AS INTEGER) AS away_fouls, "
            "CAST(NULL AS INTEGER) AS home_yellows, CAST(NULL AS INTEGER) AS away_yellows, "
            "CAST(NULL AS INTEGER) AS home_reds, CAST(NULL AS INTEGER) AS away_reds, "
            "referee, kickoff_time, CAST(NULL AS VARCHAR) AS stage, venue, source, event_kind, fetched_at, event_id "
            "FROM recent_events WHERE event_kind IN ('fixture', 'next') AND match_date >= current_date "
            "ORDER BY league, season, match_date, home_team, away_team, event_id"
        )
        if not events.empty:
            events["home_key"] = events.home_team.map(team_key)
            events["away_key"] = events.away_team.map(team_key)
            events["fixture_priority"] = (events.event_kind == "fixture").astype(int)
            events = events.sort_values(
                ["fixture_priority", "fetched_at", "event_id"], ascending=[False, False, True],
            ).drop_duplicates(
                ["competition", "season", "home_key", "away_key"], keep="first",
            ).drop(columns=["event_kind", "home_key", "away_key", "fixture_priority", "fetched_at", "event_id"])
        else:
            events = events.drop(columns=["event_kind", "fetched_at", "event_id"])
        frames.append(events)
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


def shot_analysis(
    store: ReadOnlyStore,
    competition: str | None = None,
    season: int | None = None,
    team: str | None = None,
) -> ShotAnalysisResponse:
    """Expose nullable shot analysis only after the 95% coverage gate."""
    frames = []
    for table in ("mart_dashboard_match", "recent_matches"):
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
        ("fct_match_timeline_event", "timeline_count"),
        ("fct_match_lineup", "lineup_count"),
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
        "SELECT * FROM fct_match_timeline_event WHERE event_id = ? ORDER BY try_cast(minute AS INTEGER) NULLS LAST, timeline_id",
        [str(event_id)],
    ) if _has(store, "fct_match_timeline_event") else pd.DataFrame()
    lineups = store.query(
        "SELECT * FROM fct_match_lineup WHERE event_id = ? ORDER BY is_home DESC, is_substitute, team, player",
        [str(event_id)],
    ) if _has(store, "fct_match_lineup") else pd.DataFrame()
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


def _stored_timeline(store: ReadOnlyStore, event_id: str, source: str) -> list[EventTimelineItem]:
    if not _has(store, "fct_match_timeline_event"):
        return []
    rows = store.query(
        "SELECT * FROM fct_match_timeline_event WHERE source = ? AND event_id = ? "
        "ORDER BY try_cast(minute AS INTEGER) NULLS LAST, timeline_id",
        [source, str(event_id)],
    )
    media = _team_media_map(store)
    return [EventTimelineItem(
        minute=_present(row.minute), event_type=_present(row.event_type),
        detail=_present(row.detail), team=_build_team_ref(row.team, media),
        player_id=_present(row.player_id), player=_present(row.player),
        assist=_present(row.assist),
        is_home=None if pd.isna(row.is_home) else bool(row.is_home),
        comment=_present(row.comment),
    ) for row in rows.itertuples(index=False)]


def _stored_lineups(store: ReadOnlyStore, event_id: str, source: str) -> list[EventLineupItem]:
    if not _has(store, "fct_match_lineup"):
        return []
    rows = store.query(
        "SELECT * FROM fct_match_lineup WHERE source = ? AND event_id = ? "
        "ORDER BY is_home DESC, is_substitute, team, position, player",
        [source, str(event_id)],
    )
    media = _team_media_map(store)
    return [EventLineupItem(
        team=_build_team_ref(row.team, media), player_id=_present(row.player_id),
        player=_present(row.player), position=_present(row.position),
        is_home=None if pd.isna(row.is_home) else bool(row.is_home),
        is_substitute=None if pd.isna(row.is_substitute) else bool(row.is_substitute),
        shirt_number=_present(row.shirt_number), cutout_url=_present(row.cutout_url),
    ) for row in rows.itertuples(index=False)]


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
    listing = list_matches(
        store, competition=competition, season=season, team=home,
        opponent=away, limit=200,
    )
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
    if _has(store, "fct_match_context"):
        candidates = store.query(
            "SELECT * FROM fct_match_context WHERE match_date = ? ORDER BY fetched_at DESC",
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
    context_event_id = _present(getattr(context, "match_id", None))
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
    for name, home_value, away_value in stored_statistics:
        if (home_value is not None or away_value is not None) and name.casefold() not in known_stats:
            statistics.append(EventStatistic(
                statistic=name,
                home_value=None if home_value is None else float(home_value),
                away_value=None if away_value is None else float(away_value),
            ))

    transfermarkt_timeline = (
        _stored_timeline(store, context_event_id, "Transfermarkt Open Dataset")
        if context_event_id else []
    )
    timeline = transfermarkt_timeline or (list(provider_detail.timeline) if provider_detail else [])
    if not timeline and competition in TOURNAMENTS and _has(store, "fct_tournament_goal"):
        goals = store.query(
            "SELECT * FROM fct_tournament_goal WHERE competition = ? AND season = ? AND match_date = ?",
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

    transfermarkt_lineups = (
        _stored_lineups(store, context_event_id, "Transfermarkt Open Dataset")
        if context_event_id else []
    )
    lineups = transfermarkt_lineups or (list(provider_detail.lineups) if provider_detail else [])

    # Prefer verified event counts over a missing/incorrect aggregate without erasing
    # a larger provider total. A second yellow is a sending-off as well as a card event.
    for name, matcher in (
        ("Yellow cards", lambda value: "yellow" in value),
        ("Red cards", lambda value: "red card" in value or "second yellow" in value),
    ):
        home_count = sum(item.is_home is True and matcher((item.event_type or "").casefold()) for item in timeline)
        away_count = sum(item.is_home is False and matcher((item.event_type or "").casefold()) for item in timeline)
        if home_count or away_count:
            existing = next((item for item in statistics if item.statistic.casefold() == name.casefold()), None)
            if existing:
                existing.home_value = float(max(home_count, int(existing.home_value or 0)))
                existing.away_value = float(max(away_count, int(existing.away_value or 0)))
            else:
                statistics.append(EventStatistic(
                    statistic=name, home_value=float(home_count), away_value=float(away_count),
                ))
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
        event_id=event_id or context_event_id,
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
