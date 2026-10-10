import type { RankingRow } from '@/lib/api/types';

/** Sort accessors shared by every table built from ranking rows (standings, analysis, club history). */
export const RANKING_COLUMNS = {
  rank: (r: RankingRow) => r.rank,
  team: (r: RankingRow) => r.team.name,
  season: (r: RankingRow) => r.season,
  competition: (r: RankingRow) => r.competition,
  played: (r: RankingRow) => r.played,
  wins: (r: RankingRow) => r.wins,
  draws: (r: RankingRow) => r.draws,
  losses: (r: RankingRow) => r.losses,
  goalsFor: (r: RankingRow) => r.goals_for,
  goalsAgainst: (r: RankingRow) => r.goals_against,
  goalDifference: (r: RankingRow) => r.goal_difference,
  points: (r: RankingRow) => r.points,
  ppg: (r: RankingRow) => r.points_per_game,
  gfPerGame: (r: RankingRow) => r.goals_per_game,
  gaPerGame: (r: RankingRow) => r.conceded_per_game,
  winRate: (r: RankingRow) => r.win_rate,
  cleanSheets: (r: RankingRow) => r.clean_sheet_rate,
  formPpg: (r: RankingRow) => r.form_ppg,
};

export const rankingSearch = (r: RankingRow) => [r.team.name, r.competition];
