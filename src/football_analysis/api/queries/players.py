"""Players and transfers."""

from __future__ import annotations


import pandas as pd

from football_analysis.api.contracts import (
    PageMeta,
    PlayerListResponse,
    PlayerProfileResponse,
    PlayerStat,
    PlayerSummary,
    TransferListResponse,
    TransferRow,
)
from football_analysis.api.db import ReadOnlyStore
from football_analysis.api.pagination import decode_cursor, encode_cursor
from football_analysis.teams import display_team, team_key
from football_analysis.api.queries._shared import (
    _as_date,
    _build_team_ref,
    _fuzzy_score,
    _has,
    _source,
    _team_media_map,
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
    if not _has(store, "dim_player"):
        return PlayerListResponse(
            players=[], page=PageMeta(next_cursor=None, limit=limit, returned=0),
            source=_source("transfermarkt-open", "empty"),
        )
    frame = store.query(
        "SELECT source, player_id, team, player, position, nationality, date_born, "
        "data_as_of, image_url, market_value_eur FROM dim_player"
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
        frame = frame[frame._search_score >= 0.75]
    if sort_by == "market_value":
        frame = frame[frame.market_value_eur.notna()].sort_values(
            ["market_value_eur", "player", "player_id"], ascending=[False, True, True]
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
    by_value = sort_by == "market_value"
    token = decode_cursor(cursor, required=("n", "id", "v") if by_value else ("n", "id"))
    if token:
        if token.get("s") != sort_by:
            raise ValueError("Cursor belongs to a different sort order")
        after_name = (frame.player > token["n"]) | ((frame.player == token["n"]) & (frame.player_id > token["id"]))
        if by_value:
            value = frame.market_value_eur.astype(float)
            after_name = (value < token["v"]) | ((value == token["v"]) & after_name)
        frame = frame[after_name]
    page = frame.head(limit + 1)
    has_more = len(page) > limit
    page = page.head(limit)
    next_cursor = None
    if has_more and not page.empty:
        last = page.iloc[-1]
        next_cursor = encode_cursor({"n": last.player, "id": last.player_id, "s": sort_by,
                                     **({"v": float(last.market_value_eur)} if by_value else {})})
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
    if not _has(store, "dim_player"):
        return None
    frame = store.query("SELECT * FROM dim_player WHERE player_id = ?", [player_id])
    if frame.empty:
        return None
    row = frame.iloc[0]
    stats: list[PlayerStat] = []
    if _has(store, "fct_player_competition_season"):
        stat_frame = store.query(
            "SELECT * FROM fct_player_competition_season WHERE player_id = ?",
            [player_id],
        )
        stat_frame = stat_frame.sort_values(["season", "competition"], ascending=[False, True], kind="stable")
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
    if not _has(store, "fct_transfer"):
        return TransferListResponse(
            transfers=[], total_count=0,
            page=PageMeta(next_cursor=None, limit=limit, returned=0),
            source=_source("transfermarkt-open", "empty"),
        )

    sql = " FROM fct_transfer WHERE 1=1"
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

    total_count = int(store.scalar("SELECT count(*)" + sql, params) or 0)
    token = decode_cursor(cursor, required=("off",))
    offset = int(token["off"]) if token else 0
    # ponytail: offset cursor (the order has no cheap keyset with NULLS LAST); rows may shift if data changes mid-scroll.
    sql += (" ORDER BY market_value_eur DESC NULLS LAST, transfer_fee DESC NULLS LAST, transfer_date DESC NULLS LAST, "
            f"transfer_id LIMIT {limit} OFFSET {max(0, offset)}")
    page = store.query("SELECT *" + sql, params)
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
        page=PageMeta(next_cursor=encode_cursor({"off": offset + len(rows)}) if offset + len(rows) < total_count else None,
                      limit=limit, returned=len(rows)),
        source=_source("transfermarkt-open", "transfers"),
    )
