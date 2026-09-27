"""Versioned JSON contracts for the FastAPI v1 surface."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from football_analysis.teams import display_team, team_key


def canonical_team_id(name: str | None) -> str:
    """Stable URL identity; never use a display name as a path segment."""
    return team_key(name or "")


class TeamRef(BaseModel):
    team_id: str
    name: str
    badge_url: str | None = None
    logo_url: str | None = None

    @classmethod
    def from_name(cls, name: str | None, badge_url: str | None = None, logo_url: str | None = None) -> "TeamRef":
        raw = name or ""
        return cls(team_id=canonical_team_id(raw), name=display_team(raw) or raw, badge_url=badge_url, logo_url=logo_url)


class SourceMeta(BaseModel):
    source: str
    coverage: str
    freshness: datetime | date | str | None = None


class SeasonCoverage(BaseModel):
    season: int
    label: str
    match_count: int
    latest_match: date | None = None
    status: Literal["complete", "live_partial", "missing"] = "complete"


class Competition(BaseModel):
    code: str
    name: str
    kind: Literal["domestic", "tournament"]
    group: str = "Other competitions"
    region: str | None = None
    seasons: list[SeasonCoverage] = Field(default_factory=list)
    source: SourceMeta | None = None
    badge_url: str | None = None
    logo_url: str | None = None
    banner_url: str | None = None
    trophy_url: str | None = None
    fanart_url: str | None = None


class CatalogResponse(BaseModel):
    competitions: list[Competition]
    current_season: int
    generated_at: datetime
    source: SourceMeta


class Team(TeamRef):
    competition: str
    season: int
    played: int = 0
    points: int = 0


class TeamListResponse(BaseModel):
    teams: list[Team]
    source: SourceMeta


class Match(BaseModel):
    competition: str
    season: int
    match_date: date
    kickoff_time: str | None = None
    home: TeamRef
    away: TeamRef
    home_goals: int | None = None
    away_goals: int | None = None
    venue: str | None = None
    stage: str | None = None
    referee: str | None = None
    home_shots: int | None = None
    away_shots: int | None = None
    home_shots_on_target: int | None = None
    away_shots_on_target: int | None = None
    half_time_home_goals: int | None = None
    half_time_away_goals: int | None = None
    home_corners: int | None = None
    away_corners: int | None = None
    home_fouls: int | None = None
    away_fouls: int | None = None
    home_yellows: int | None = None
    away_yellows: int | None = None
    home_reds: int | None = None
    away_reds: int | None = None
    source: str | None = None


class PageMeta(BaseModel):
    next_cursor: str | None = None
    limit: int
    returned: int


class MatchListResponse(BaseModel):
    matches: list[Match]
    page: PageMeta
    source: SourceMeta


class ShotCoverageRow(BaseModel):
    competition: str
    season: int
    matches: int
    shot_matches: int
    coverage_pct: float


class ShotEfficiencyRow(BaseModel):
    competition: str
    season: int
    team: TeamRef
    matches: int
    coverage_pct: float
    shots_per_match: float | None = None
    shot_accuracy_pct: float | None = None
    goals_per_shot_pct: float | None = None
    goals_per_sot_pct: float | None = None


class ShotAnalysisResponse(BaseModel):
    coverage: list[ShotCoverageRow] = Field(default_factory=list)
    teams: list[ShotEfficiencyRow] = Field(default_factory=list)
    source: SourceMeta


class EventSummary(BaseModel):
    event_id: str
    competition: str
    season: int
    match_date: date
    home: TeamRef
    away: TeamRef
    home_goals: int | None = None
    away_goals: int | None = None
    status: str | None = None
    statistics_count: int = 0
    timeline_count: int = 0
    lineup_count: int = 0


class EventStatistic(BaseModel):
    statistic: str
    home_value: float | None = None
    away_value: float | None = None


class EventTimelineItem(BaseModel):
    minute: str | None = None
    event_type: str | None = None
    detail: str | None = None
    team: TeamRef
    player_id: str | None = None
    player: str | None = None
    assist: str | None = None
    is_home: bool | None = None
    comment: str | None = None


class EventLineupItem(BaseModel):
    team: TeamRef
    player_id: str | None = None
    player: str | None = None
    position: str | None = None
    is_home: bool | None = None
    is_substitute: bool | None = None
    shirt_number: str | None = None
    cutout_url: str | None = None


class EventListResponse(BaseModel):
    events: list[EventSummary] = Field(default_factory=list)
    source: SourceMeta


class EventDetailResponse(BaseModel):
    event: EventSummary
    statistics: list[EventStatistic] = Field(default_factory=list)
    timeline: list[EventTimelineItem] = Field(default_factory=list)
    lineups: list[EventLineupItem] = Field(default_factory=list)
    source: SourceMeta


class MatchCentreDetailResponse(BaseModel):
    match: Match
    event_id: str | None = None
    status: str | None = None
    home_coach: str | None = None
    away_coach: str | None = None
    home_formation: str | None = None
    away_formation: str | None = None
    stadium: str | None = None
    attendance: int | None = None
    statistics: list[EventStatistic] = Field(default_factory=list)
    timeline: list[EventTimelineItem] = Field(default_factory=list)
    lineups: list[EventLineupItem] = Field(default_factory=list)
    narrative: list[str] = Field(default_factory=list)
    lineup_complete: bool = False
    coverage_notes: list[str] = Field(default_factory=list)
    source: SourceMeta


class AnalysisFilters(BaseModel):
    competitions: list[str] = Field(default_factory=list)
    seasons: list[int] = Field(default_factory=list)
    teams: list[str] = Field(default_factory=list)
    venue: str | None = None
    form_window: int = 5


class RankingRow(BaseModel):
    competition: str
    season: int
    team: TeamRef
    rank: int
    played: int
    wins: int
    draws: int
    losses: int
    points: int
    goals_for: int
    goals_against: int
    goal_difference: int
    points_per_game: float
    goals_per_game: float
    conceded_per_game: float
    win_rate: float
    clean_sheet_rate: float
    form: str | None = None
    form_ppg: float | None = None


class FormRow(BaseModel):
    competition: str
    season: int
    team: TeamRef
    form_matches: int
    form_points: int
    form_goals_for: int
    form_goals_against: int
    form: str
    form_ppg: float


class CorrelationRow(BaseModel):
    model_config = ConfigDict(extra="allow")
    metric: str


class RefereeSummary(BaseModel):
    referee: str
    matches: int
    yellow_cards_mean: float | None = None
    red_cards_mean: float | None = None


class MatchFactorSummary(BaseModel):
    first_half_goals_mean: float | None = None
    second_half_goals_mean: float | None = None
    corners_mean: float | None = None
    fouls_mean: float | None = None
    yellow_cards_mean: float | None = None
    red_cards_mean: float | None = None
    referees: list[RefereeSummary] = Field(default_factory=list)


class AnalysisRequestBody(AnalysisFilters):
    pass


class EloRatingRow(BaseModel):
    team: TeamRef
    season: int
    league: str
    post_elo: float


class AnalysisReportResponse(BaseModel):
    filters: AnalysisFilters
    match_count: int
    rankings: list[RankingRow]
    form: list[FormRow]
    correlations: list[CorrelationRow]
    match_factors: MatchFactorSummary
    elo_ratings: list[EloRatingRow] = Field(default_factory=list)
    source: SourceMeta


class TournamentMatch(Match):
    group_name: str | None = None
    home_penalties: int | None = None
    away_penalties: int | None = None
    status: str | None = None


class TournamentGoal(BaseModel):
    match_date: date
    team: TeamRef
    player: str
    minute: str | None = None
    penalty: bool = False
    own_goal: bool = False


class TournamentStage(BaseModel):
    stage: str
    match_count: int


class TournamentResponse(BaseModel):
    competition: str
    name: str
    season: int
    stages: list[TournamentStage]
    matches: list[TournamentMatch]
    scorers: list[TournamentGoal]
    source: SourceMeta


class PlayerStat(BaseModel):
    season: int | str | None = None
    competition: str | None = None
    statistic: str
    value: float | None = None
    appearances: int | None = None
    goals: int | None = None
    assists: int | None = None
    minutes_played: int | None = None
    yellow_cards: int | None = None
    red_cards: int | None = None


class PlayerSummary(BaseModel):
    player_id: str
    name: str
    team: TeamRef
    position: str | None = None
    nationality: str | None = None
    image_url: str | None = None
    market_value_eur: int | None = None
    source: str


class PlayerListResponse(BaseModel):
    players: list[PlayerSummary]
    page: PageMeta
    total_count: int = 0
    teams: list[TeamRef] = Field(default_factory=list)
    positions: list[str] = Field(default_factory=list)
    average_age: float | None = None
    nationality_count: int = 0
    total_market_value_eur: int = 0
    source: SourceMeta


class PlayerProfileResponse(BaseModel):
    player_id: str
    name: str
    team: TeamRef
    position: str | None = None
    sub_position: str | None = None
    nationality: str | None = None
    date_born: date | None = None
    height_cm: int | None = None
    foot: str | None = None
    market_value_eur: int | None = None
    image_url: str | None = None
    source: str
    stats: list[PlayerStat] = Field(default_factory=list)
    coverage: SourceMeta


class Forecast(BaseModel):
    competition: str
    season: int
    match_date: date
    home: TeamRef
    away: TeamRef
    predicted_result: str
    home_probability: float
    draw_probability: float
    away_probability: float


class CalibrationBin(BaseModel):
    predicted_outcome: str
    mean_probability: float
    observed_rate: float
    samples: int


class ForecastAuditRow(Forecast):
    model_id: str
    issued_at: datetime
    actual_result: str | None = None
    resolved_at: datetime | None = None


class LeagueTitleOutlook(BaseModel):
    competition: str
    season: int
    team: TeamRef
    current_rank: int
    played: int
    points: int
    projected_points: float
    title_probability: float


class PredictionsResponse(BaseModel):
    model_id: str | None = None
    model_name: str | None = None
    trained_at: datetime | None = None
    validation_cutoff: date | None = None
    metrics: dict[str, Any] = Field(default_factory=dict)
    calibration: list[CalibrationBin] = Field(default_factory=list)
    forecasts: list[Forecast] = Field(default_factory=list)
    forecast_history: list[ForecastAuditRow] = Field(default_factory=list)
    forecast_record: dict[str, Any] = Field(default_factory=dict)
    league_outlooks: list[LeagueTitleOutlook] = Field(default_factory=list)
    source: SourceMeta


class ClubSpotlight(BaseModel):
    team: TeamRef
    league: str
    season: int
    played: int = 0
    wins: int = 0
    draws: int = 0
    losses: int = 0
    points: int = 0
    points_per_game: float = 0.0
    goal_difference: int = 0
    latest_match: Match | None = None
    previous_match: Match | None = None
    next_match: Match | None = None
    next_fixture: Forecast | None = None


class OverviewResponse(BaseModel):
    spotlight: ClubSpotlight | None = None
    performance_over_time: list[RankingRow] = Field(default_factory=list)
    elo_trajectory: list[EloRatingRow] = Field(default_factory=list)
    forecasts: list[Forecast] = Field(default_factory=list)
    source: SourceMeta


class QualityCell(BaseModel):
    competition: str
    season: int
    status: str
    match_count: int = 0


class FixtureCoverageRow(BaseModel):
    competition: str
    full_schedule: int = 0
    weekly_window: int = 0
    next_listed: int = 0
    latest_fetched_at: datetime | None = None


class QualityResponse(BaseModel):
    completed_coverage: str
    live_competitions: str
    match_records: int
    impossible_shot_rows: int
    reference_rows: int = 0
    recent_competitions: int = 0
    completed_results: int = 0
    tracked_players: int = 0
    player_clubs: int = 0
    player_stat_rows: int = 0
    artwork_rows: int = 0
    tournament_matches: int = 0
    tournament_teams: int = 0
    tournament_breakdown: dict[str, int] = Field(default_factory=dict)
    context_rich_matches: int = 0
    match_context_rows: int = 0
    formation_rows: int = 0
    coach_rows: int = 0
    tournament_goals: int = 0
    detailed_event_stats: int = 0
    timeline_events: int = 0
    lineup_rows: int = 0
    model_predictions: int = 0
    fixture_coverage: list[FixtureCoverageRow] = Field(default_factory=list)
    source_caps: list[str] = Field(default_factory=list)
    null_coverage: dict[str, float] = Field(default_factory=dict)
    checksums: list[dict[str, Any]] = Field(default_factory=list)
    refresh_timestamps: dict[str, datetime | str | None] = Field(default_factory=dict)
    grid: list[QualityCell] = Field(default_factory=list)
    shot_coverage: list[ShotCoverageRow] = Field(default_factory=list)
    source: SourceMeta


class ReferenceStandingRow(BaseModel):
    competition: str
    season: int
    source_name: str
    rank: int
    team: TeamRef
    played: int | None = None
    points: int | None = None
    goal_difference: int | None = None
    form: str | None = None
    description: str | None = None
    source_updated_at: datetime | None = None
    fetched_at: datetime | None = None
    results_rank: int | None = None
    results_points: int | None = None
    results_goal_difference: int | None = None
    point_adjustment: int | None = None
    rank_difference: int | None = None


class StandingsResponse(BaseModel):
    competition: str
    season: int
    rankings: list[RankingRow] = Field(default_factory=list)
    reference: list[ReferenceStandingRow] = Field(default_factory=list)
    source: SourceMeta


class HealthResponse(BaseModel):
    status: Literal["ok", "degraded", "unavailable"]
    database: str
    read_only: bool


class TransferRow(BaseModel):
    transfer_id: str
    player_id: str
    player_name: str
    transfer_date: date | None = None
    transfer_season: str
    season: int
    from_club: TeamRef
    to_club: TeamRef
    transfer_fee: float | None = None
    market_value_eur: int | None = None
    from_competition: str | None = None
    to_competition: str | None = None
    image_url: str | None = None


class TransferListResponse(BaseModel):
    transfers: list[TransferRow]
    total_count: int
    page: PageMeta
    source: SourceMeta


class RefreshRequest(BaseModel):
    target_step: int = Field(default=4, ge=1, le=4)
    season: int | None = None
    competitions: list[str] = Field(default_factory=list)
    force_download: bool = False


class RefreshSourceOutcome(BaseModel):
    step: int
    source: str
    partition: str | None = None
    status: str
    required: bool = False
    detail: str | None = None


class RefreshStatusResponse(BaseModel):
    job_id: str | None = None
    status: Literal["idle", "running", "success", "degraded", "failed"] = "idle"
    current_step: int = 0
    target_step: int = 4
    completed_steps: list[int] = Field(default_factory=list)
    step_name: str = "Ready"
    message: str = "Choose a refresh depth to begin."
    started_at: datetime | None = None
    finished_at: datetime | None = None
    error: str | None = None
    failed_count: int = 0
    degraded_count: int = 0
    source_messages: list[str] = Field(default_factory=list)
    source_outcomes: list[RefreshSourceOutcome] = Field(default_factory=list)
