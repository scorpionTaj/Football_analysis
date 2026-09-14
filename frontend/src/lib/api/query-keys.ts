/** Centralized query keys for TanStack Query cache management. */

export const queryKeys = {
  health: ['health'] as const,
  catalog: ['catalog'] as const,
  teams: (competition?: string, season?: number) =>
    ['teams', { competition, season }] as const,
  matches: (filters: Record<string, unknown>) =>
    ['matches', filters] as const,
  analysis: (filters: Record<string, unknown>) =>
    ['analysis', filters] as const,
  tournament: (competition: string, season: number) =>
    ['tournament', competition, season] as const,
  predictions: ['predictions'] as const,
  players: (filters: Record<string, unknown>) =>
    ['players', filters] as const,
  player: (id: string) => ['player', id] as const,
  quality: ['quality'] as const,
  overview: (opts?: { team?: string; competition?: string; season?: number }) =>
    ['overview', opts || {}] as const,
} as const;

