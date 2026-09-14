/** Centralized API client for the FastAPI v1 backend. */

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export class ApiError extends Error {
  constructor(
    public status: number,
    public detail: string,
  ) {
    super(`API ${status}: ${detail}`);
    this.name = 'ApiError';
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const url = `${API_BASE}${path}`;
  const res = await fetch(url, {
    ...init,
    headers: {
      'Content-Type': 'application/json',
      ...init?.headers,
    },
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: res.statusText }));
    throw new ApiError(res.status, body.detail || res.statusText);
  }
  return res.json() as Promise<T>;
}

function params(obj: Record<string, string | number | null | undefined>): string {
  const entries = Object.entries(obj).filter(
    ([, v]) => v !== null && v !== undefined && v !== '',
  );
  if (entries.length === 0) return '';
  return '?' + new URLSearchParams(entries.map(([k, v]) => [k, String(v)])).toString();
}

// ---- typed endpoint functions ----

import type {
  AnalysisFilters,
  AnalysisReportResponse,
  CatalogResponse,
  EventDetailResponse,
  EventListResponse,
  HealthResponse,
  MatchListResponse,
  OverviewResponse,
  PlayerListResponse,
  PlayerProfileResponse,
  PredictionsResponse,
  QualityResponse,
  ShotAnalysisResponse,
  TeamListResponse,
  TournamentResponse,
  TransferListResponse,
} from './types';

export const api = {
  health: () => request<HealthResponse>('/api/v1/health'),

  catalog: () => request<CatalogResponse>('/api/v1/catalog'),

  teams: (competition?: string, season?: number) =>
    request<TeamListResponse>(`/api/v1/teams${params({ competition, season })}`),

  matches: (opts?: {
    competition?: string;
    season?: number;
    team?: string;
    venue?: string;
    cursor?: string;
    limit?: number;
  }) => request<MatchListResponse>(`/api/v1/matches${params(opts || {})}`),

  shots: (opts?: { competition?: string; season?: number; team?: string }) =>
    request<ShotAnalysisResponse>(`/api/v1/shots${params(opts || {})}`),

  eventDetails: (opts?: { competition?: string; season?: number }) =>
    request<EventListResponse>(`/api/v1/event-details${params(opts || {})}`),

  eventDetail: (eventId: string) =>
    request<EventDetailResponse>(`/api/v1/event-details/${encodeURIComponent(eventId)}`),

  analysis: (body: Partial<AnalysisFilters>) =>
    request<AnalysisReportResponse>('/api/v1/analysis', {
      method: 'POST',
      body: JSON.stringify({
        competitions: body.competitions || [],
        seasons: body.seasons || [],
        teams: body.teams || [],
        venue: body.venue || null,
        form_window: body.form_window || 5,
      }),
    }),

  tournament: (competition: string, season: number) =>
    request<TournamentResponse>(`/api/v1/tournaments/${competition}/${season}`),

  predictions: () => request<PredictionsResponse>('/api/v1/predictions'),

  players: (opts?: { q?: string; team?: string; sort_by?: string; cursor?: string; limit?: number }) =>
    request<PlayerListResponse>(`/api/v1/players${params(opts || {})}`),

  player: (playerId: string) =>
    request<PlayerProfileResponse>(`/api/v1/players/${playerId}`),

  quality: () => request<QualityResponse>('/api/v1/quality'),

  overview: (opts?: { team?: string; competition?: string; season?: number }) =>
    request<OverviewResponse>(`/api/v1/overview${params(opts || {})}`),

  transfers: (opts?: {
    season?: number;
    competition?: string;
    club?: string;
    q?: string;
    cursor?: string;
    limit?: number;
  }) => request<TransferListResponse>(`/api/v1/transfers${params(opts || {})}`),
};
