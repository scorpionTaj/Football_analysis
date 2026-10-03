/** Centralized query keys for TanStack Query cache management. */

export const queryKeys = {
  health: ['health'] as const,
  catalog: ['catalog'] as const,
  teams: (competition?: string, season?: number) =>
    ['teams', { competition, season }] as const,
  matches: (filters: Record<string, unknown>) =>
    ['matches', filters] as const,
  shots: (filters: Record<string, unknown>) =>
    ['shots', filters] as const,
  eventDetails: (filters: Record<string, unknown>) =>
    ['event-details', filters] as const,
  eventDetail: (id: string) => ['event-detail', id] as const,
  matchDetail: (match: Record<string, unknown>) => ['match-detail', match] as const,
  analysis: (filters: Record<string, unknown>) =>
    ['analysis', filters] as const,
  tournament: (competition: string, season: number) =>
    ['tournament', competition, season] as const,
  predictions: ['predictions'] as const,
  models: ['models'] as const,
  players: (filters: Record<string, unknown>) =>
    ['players', filters] as const,
  player: (id: string) => ['player', id] as const,
  quality: ['quality'] as const,
  standings: (competition: string, season: number, formWindow: number, venue?: string) =>
    ['standings', competition, season, formWindow, venue] as const,
  overview: (opts?: { team?: string; competition?: string; season?: number }) =>
    ['overview', opts || {}] as const,
  transfers: (opts?: Record<string, unknown>) =>
    ['transfers', opts || {}] as const,
  refreshStatus: ['refresh-status'] as const,
} as const;
