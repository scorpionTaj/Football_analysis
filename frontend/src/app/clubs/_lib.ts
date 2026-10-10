import type { Match, RankingRow } from '@/lib/api/types';

export type ClubTotals = ReturnType<typeof summarize>;

/** All-seasons totals for one club's ranking rows (clean-sheet rate weighted by matches played). */
export function summarize(rows: readonly RankingRow[]) {
  const sum = (pick: (row: RankingRow) => number) => rows.reduce((total, row) => total + pick(row), 0);
  const played = sum((row) => row.played);
  const wins = sum((row) => row.wins);
  const points = sum((row) => row.points);
  const goalsFor = sum((row) => row.goals_for);
  const goalsAgainst = sum((row) => row.goals_against);
  const rate = (value: number, digits: number) => (played > 0 ? (value / played).toFixed(digits) : '0');
  return {
    played,
    wins,
    draws: sum((row) => row.draws),
    losses: sum((row) => row.losses),
    points,
    goalsFor,
    goalsAgainst,
    ppg: rate(points, 2),
    winRate: rate(wins * 100, 1),
    gfPerMatch: rate(goalsFor, 2),
    gaPerMatch: rate(goalsAgainst, 2),
    cleanSheetRate: rate(sum((row) => row.clean_sheet_rate * row.played), 1),
  };
}

/** The club's goals, the opponent's goals and the W/D/L letter, from the club's side. */
export function fromClubSide(match: Match, isHome: boolean) {
  const own = isHome ? match.home_goals : match.away_goals;
  const other = isHome ? match.away_goals : match.home_goals;
  const result = own === null || other === null ? null : own > other ? 'W' : own === other ? 'D' : 'L';
  return { own, other, result } as const;
}

export const seasonLabel = (season: number) => `${season}/${String(season + 1).slice(2)}`;
