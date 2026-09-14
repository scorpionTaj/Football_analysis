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
    home: TeamRef
    away: TeamRef
    home_goals: int | None = None
    away_goals: int | None = None
    venue: str | None = None
    stage: str | None = None
    referee: str | None = None
    source: str | None = None


class PageMeta(BaseModel):
    next_cursor: str | None = None
    limit: int
    returned: int


class MatchListResponse(BaseModel):
    matches: list[Match]
    page: PageMeta
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


class PredictionsResponse(BaseModel):
    model_id: str | None = None
    model_name: str | None = None
    trained_at: datetime | None = None
    validation_cutoff: date | None = None
    metrics: dict[str, Any] = Field(default_factory=dict)
    calibration: list[CalibrationBin] = Field(default_factory=list)
    forecasts: list[Forecast] = Field(default_factory=list)
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


class QualityResponse(BaseModel):
    completed_coverage: str
    live_competitions: str
    match_records: int
    impossible_shot_rows: int
    source_caps: list[str] = Field(default_factory=list)
    null_coverage: dict[str, float] = Field(default_factory=dict)
    checksums: list[dict[str, Any]] = Field(default_factory=list)
    refresh_timestamps: dict[str, datetime | str | None] = Field(default_factory=dict)
    grid: list[QualityCell] = Field(default_factory=list)
    source: SourceMeta


class HealthResponse(BaseModel):
    status: Literal["ok", "degraded", "unavailable"]
    database: str
    read_only: bool
