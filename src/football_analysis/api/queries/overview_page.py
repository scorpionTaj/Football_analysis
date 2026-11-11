"""The Overview page: one club's season at a glance."""

from __future__ import annotations



from football_analysis.api.contracts import (
    AnalysisFilters,
    ClubSpotlight,
    OverviewResponse,
)
from football_analysis.api.db import ReadOnlyStore
from football_analysis.config import (
    TOURNAMENTS,
    current_season,
    seasons,
)
from football_analysis.teams import team_key
from football_analysis.api.queries._shared import (
    _build_team_ref,
    _has,
    _match_from_row,
    _source,
    _store_source,
    _team_media_map,
)
from football_analysis.api.queries.analysis import (
    build_analysis,
)
from football_analysis.api.queries.forecasts import (
    predictions,
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
    if _has(store, "fct_tournament_match") and competition in TOURNAMENTS:
        try:
            t_years = store.query("SELECT DISTINCT season FROM fct_tournament_match WHERE competition = ?", [competition])["season"].tolist()
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
        SELECT league, season, match_date, home_team, away_team, home_goals, away_goals, referee, 'football-data.co.uk' AS source FROM mart_dashboard_match WHERE home_goals IS NOT NULL
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
            "SELECT * FROM recent_events WHERE season = ? AND event_kind IN ('next', 'fixture') "
            "AND match_date >= current_date ORDER BY match_date, event_kind, event_id",
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
        # Only this competition's next fixtures; the full slate lives on /predictions.
        forecasts=[f for f in preds.forecasts if f.competition == competition][:20],
        source=_source(_store_source(store), "overview"),
    )
