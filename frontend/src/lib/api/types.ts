/** API v1 response types — mirrors src/football_analysis/api/contracts.py */

export interface TeamRef {
  team_id: string;
  name: string;
  badge_url?: string | null;
  logo_url?: string | null;
}

export interface SourceMeta {
  source: string;
  coverage: string;
  freshness: string | null;
}

export interface SeasonCoverage {
  season: number;
  label: string;
  match_count: number;
  latest_match: string | null;
  status: 'complete' | 'live_partial' | 'missing';
}

export interface Competition {
  code: string;
  name: string;
  kind: 'domestic' | 'tournament';
  group: string;
  region: string | null;
  seasons: SeasonCoverage[];
  badge_url?: string | null;
  logo_url?: string | null;
  banner_url?: string | null;
  trophy_url?: string | null;
  fanart_url?: string | null;
  source: SourceMeta | null;
}

export interface CatalogResponse {
  competitions: Competition[];
  current_season: number;
  generated_at: string;
  source: SourceMeta;
}

export interface Team extends TeamRef {
  competition: string;
  season: number;
  played: number;
  points: number;
}

export interface TeamListResponse {
  teams: Team[];
  source: SourceMeta;
}

export interface Match {
  competition: string;
  season: number;
  match_date: string;
  home: TeamRef;
  away: TeamRef;
  home_goals: number | null;
  away_goals: number | null;
  venue: string | null;
  stage: string | null;
  referee: string | null;
  home_shots: number | null;
  away_shots: number | null;
  home_shots_on_target: number | null;
  away_shots_on_target: number | null;
  half_time_home_goals: number | null;
  half_time_away_goals: number | null;
  home_corners: number | null;
  away_corners: number | null;
  home_fouls: number | null;
  away_fouls: number | null;
  home_yellows: number | null;
  away_yellows: number | null;
  home_reds: number | null;
  away_reds: number | null;
  source: string | null;
}

export interface PageMeta {
  next_cursor: string | null;
  limit: number;
  returned: number;
}

export interface MatchListResponse {
  matches: Match[];
  page: PageMeta;
  source: SourceMeta;
}

export interface ShotCoverageRow {
  competition: string;
  season: number;
  matches: number;
  shot_matches: number;
  coverage_pct: number;
}

export interface ShotEfficiencyRow {
  competition: string;
  season: number;
  team: TeamRef;
  matches: number;
  coverage_pct: number;
  shots_per_match: number | null;
  shot_accuracy_pct: number | null;
  goals_per_shot_pct: number | null;
  goals_per_sot_pct: number | null;
}

export interface ShotAnalysisResponse {
  coverage: ShotCoverageRow[];
  teams: ShotEfficiencyRow[];
  source: SourceMeta;
}

export interface EventSummary {
  event_id: string;
  competition: string;
  season: number;
  match_date: string;
  home: TeamRef;
  away: TeamRef;
  home_goals: number | null;
  away_goals: number | null;
  status: string | null;
  statistics_count: number;
  timeline_count: number;
  lineup_count: number;
}

export interface EventStatistic {
  statistic: string;
  home_value: number | null;
  away_value: number | null;
}

export interface EventTimelineItem {
  minute: string | null;
  event_type: string | null;
  detail: string | null;
  team: TeamRef;
  player_id: string | null;
  player: string | null;
  assist: string | null;
  is_home: boolean | null;
  comment: string | null;
}

export interface EventLineupItem {
  team: TeamRef;
  player_id: string | null;
  player: string | null;
  position: string | null;
  is_home: boolean | null;
  is_substitute: boolean | null;
  shirt_number: string | null;
  cutout_url: string | null;
}

export interface EventListResponse {
  events: EventSummary[];
  source: SourceMeta;
}

export interface EventDetailResponse {
  event: EventSummary;
  statistics: EventStatistic[];
  timeline: EventTimelineItem[];
  lineups: EventLineupItem[];
  source: SourceMeta;
}

export interface MatchCentreDetailResponse {
  match: Match;
  event_id: string | null;
  status: string | null;
  home_coach: string | null;
  away_coach: string | null;
  home_formation: string | null;
  away_formation: string | null;
  stadium: string | null;
  attendance: number | null;
  statistics: EventStatistic[];
  timeline: EventTimelineItem[];
  lineups: EventLineupItem[];
  narrative: string[];
  lineup_complete: boolean;
  coverage_notes: string[];
  source: SourceMeta;
}

export interface RefreshRequest {
  target_step: number;
  season?: number;
  competitions: string[];
  force_download: boolean;
}

export interface RefreshStatusResponse {
  job_id: string | null;
  status: 'idle' | 'running' | 'success' | 'failed';
  current_step: number;
  target_step: number;
  completed_steps: number[];
  step_name: string;
  message: string;
  started_at: string | null;
  finished_at: string | null;
  error: string | null;
}

export interface AnalysisFilters {
  competitions: string[];
  seasons: number[];
  teams: string[];
  venue: string | null;
  form_window: number;
}

export interface RankingRow {
  competition: string;
  season: number;
  team: TeamRef;
  rank: number;
  played: number;
  wins: number;
  draws: number;
  losses: number;
  points: number;
  goals_for: number;
  goals_against: number;
  goal_difference: number;
  points_per_game: number;
  goals_per_game: number;
  conceded_per_game: number;
  win_rate: number;
  clean_sheet_rate: number;
  form: string | null;
  form_ppg: number | null;
}

export interface FormRow {
  competition: string;
  season: number;
  team: TeamRef;
  form_matches: number;
  form_points: number;
  form_goals_for: number;
  form_goals_against: number;
  form: string;
  form_ppg: number;
}

export interface CorrelationRow {
  metric: string;
  [key: string]: number | string | null;
}

export interface RefereeSummary {
  referee: string;
  matches: number;
  yellow_cards_mean: number | null;
  red_cards_mean: number | null;
}

export interface MatchFactorSummary {
  first_half_goals_mean: number | null;
  second_half_goals_mean: number | null;
  corners_mean: number | null;
  fouls_mean: number | null;
  yellow_cards_mean: number | null;
  red_cards_mean: number | null;
  referees: RefereeSummary[];
}

export interface EloRatingRow {
  team: TeamRef;
  season: number;
  league: string;
  post_elo: number;
}

export interface AnalysisReportResponse {
  filters: AnalysisFilters;
  match_count: number;
  rankings: RankingRow[];
  form: FormRow[];
  correlations: CorrelationRow[];
  match_factors: MatchFactorSummary;
  elo_ratings?: EloRatingRow[];
  source: SourceMeta;
}

export interface TournamentMatch extends Match {
  group_name: string | null;
  home_penalties: number | null;
  away_penalties: number | null;
  status: string | null;
}

export interface TournamentGoal {
  match_date: string;
  team: TeamRef;
  player: string;
  minute: string | null;
  penalty: boolean;
  own_goal: boolean;
}

export interface TournamentStage {
  stage: string;
  match_count: number;
}

export interface TournamentResponse {
  competition: string;
  name: string;
  season: number;
  stages: TournamentStage[];
  matches: TournamentMatch[];
  scorers: TournamentGoal[];
  source: SourceMeta;
}

export interface PlayerStat {
  season: number | string | null;
  competition: string | null;
  statistic: string;
  value: number | null;
  appearances: number | null;
  goals: number | null;
  assists: number | null;
  minutes_played: number | null;
  yellow_cards: number | null;
  red_cards: number | null;
}

export interface PlayerSummary {
  player_id: string;
  name: string;
  team: TeamRef;
  position: string | null;
  nationality: string | null;
  image_url?: string | null;
  market_value_eur?: number | null;
  source: string;
}

export interface ClubSpotlight {
  team: TeamRef;
  league: string;
  season: number;
  played: number;
  wins: number;
  draws: number;
  losses: number;
  points: number;
  points_per_game: number;
  goal_difference: number;
  latest_match: Match | null;
  previous_match: Match | null;
  next_match: Match | null;
  next_fixture: Forecast | null;
}

export interface OverviewResponse {
  spotlight: ClubSpotlight | null;
  performance_over_time: RankingRow[];
  elo_trajectory: EloRatingRow[];
  forecasts: Forecast[];
  source: SourceMeta;
}

export interface PlayerListResponse {
  players: PlayerSummary[];
  page: PageMeta;
  total_count: number;
  teams: TeamRef[];
  positions: string[];
  average_age: number | null;
  nationality_count: number;
  total_market_value_eur: number;
  source: SourceMeta;
}

export interface PlayerProfileResponse {
  player_id: string;
  name: string;
  team: TeamRef;
  position: string | null;
  sub_position: string | null;
  nationality: string | null;
  date_born: string | null;
  height_cm: number | null;
  foot: string | null;
  market_value_eur: number | null;
  image_url: string | null;
  source: string;
  stats: PlayerStat[];
  coverage: SourceMeta;
}

export interface Forecast {
  competition: string;
  season: number;
  match_date: string;
  home: TeamRef;
  away: TeamRef;
  predicted_result: string;
  home_probability: number;
  draw_probability: number;
  away_probability: number;
}

export interface CalibrationBin {
  predicted_outcome: string;
  mean_probability: number;
  observed_rate: number;
  samples: number;
}

export interface LeagueTitleOutlook {
  competition: string;
  season: number;
  team: TeamRef;
  current_rank: number;
  played: number;
  points: number;
  projected_points: number;
  title_probability: number;
}

export interface PredictionsResponse {
  model_id: string | null;
  model_name: string | null;
  trained_at: string | null;
  validation_cutoff: string | null;
  metrics: Record<string, unknown>;
  calibration: CalibrationBin[];
  forecasts: Forecast[];
  league_outlooks: LeagueTitleOutlook[];
  source: SourceMeta;
}

export interface QualityCell {
  competition: string;
  season: number;
  status: string;
  match_count: number;
}

export interface QualityResponse {
  completed_coverage: string;
  live_competitions: string;
  match_records: number;
  impossible_shot_rows: number;
  reference_rows: number;
  recent_competitions: number;
  completed_results: number;
  tracked_players: number;
  player_clubs: number;
  player_stat_rows: number;
  artwork_rows: number;
  tournament_matches: number;
  tournament_teams: number;
  tournament_breakdown: Record<string, number>;
  context_rich_matches: number;
  match_context_rows: number;
  formation_rows: number;
  coach_rows: number;
  tournament_goals: number;
  detailed_event_stats: number;
  timeline_events: number;
  lineup_rows: number;
  model_predictions: number;
  source_caps: string[];
  null_coverage: Record<string, number>;
  checksums: Record<string, unknown>[];
  refresh_timestamps: Record<string, string | null>;
  grid: QualityCell[];
  shot_coverage: ShotCoverageRow[];
  source: SourceMeta;
}

export interface ReferenceStandingRow {
  competition: string;
  season: number;
  source_name: string;
  rank: number;
  team: TeamRef;
  played: number | null;
  points: number | null;
  goal_difference: number | null;
  form: string | null;
  description: string | null;
  source_updated_at: string | null;
  fetched_at: string | null;
  results_rank: number | null;
  results_points: number | null;
  results_goal_difference: number | null;
  point_adjustment: number | null;
  rank_difference: number | null;
}

export interface StandingsResponse {
  competition: string;
  season: number;
  rankings: RankingRow[];
  reference: ReferenceStandingRow[];
  source: SourceMeta;
}

export interface HealthResponse {
  status: 'ok' | 'degraded' | 'unavailable';
  database: string;
  read_only: boolean;
}

export interface TransferRow {
  transfer_id: string;
  player_id: string;
  player_name: string;
  transfer_date: string | null;
  transfer_season: string;
  season: number;
  from_club: TeamRef;
  to_club: TeamRef;
  transfer_fee: number | null;
  market_value_eur: number | null;
  from_competition: string | null;
  to_competition: string | null;
  image_url: string | null;
}

export interface TransferListResponse {
  transfers: TransferRow[];
  total_count: number;
  page: PageMeta;
  source: SourceMeta;
}
