'use client';

import { useSyncExternalStore } from 'react';
import { useQuery } from '@tanstack/react-query';
import { api } from '@/lib/api/client';
import { queryKeys } from '@/lib/api/query-keys';
import { useFilterParams } from '@/lib/hooks/use-filter-params';
import { Select } from '@/components/ui/select';

const noop = () => () => {};

/** false on the server and during hydration, true afterwards — no extra effect or render pass. */
function useHydrated() {
  return useSyncExternalStore(noop, () => true, () => false);
}

/** Shared filter bar for competition, season, team, and optional venue selection. */
export function FilterBar({ showVenue = true }: { showVenue?: boolean }) {
  const filters = useFilterParams();

  const { data: catalog } = useQuery({
    queryKey: queryKeys.catalog,
    queryFn: () => api.catalog(),
  });

  const { data: teamData } = useQuery({
    queryKey: queryKeys.teams(filters.competition ?? undefined, filters.season),
    queryFn: () => api.teams(filters.competition ?? undefined, filters.season),
    enabled: !!filters.competition,
  });

  // The navigation fills the shared query cache before this Suspense subtree hydrates; render the
  // server's (empty) options until hydration finishes so the markup matches.
  const hydrated = useHydrated();
  const competitions = (hydrated && catalog?.competitions) || [];
  const selected = competitions.find((c) => c.code === filters.competition);
  const seasons = selected?.seasons ?? [];
  const teams = (hydrated && teamData?.teams) || [];

  // Deduplicate teams by team_id and sort alphabetically
  const uniqueTeams = Array.from(
    new Map(teams.map((t) => [t.team_id, t])).values(),
  ).sort((a, b) => a.name.localeCompare(b.name));

  return (
    <div className="grid grid-cols-2 gap-3 sm:flex sm:flex-wrap sm:items-end">
      {/* Competition selector */}
      <Select
        label="Competition"
        value={filters.competition ?? ''}
        onChange={(v) => {
          const comp = competitions.find((c) => c.code === v);
          const latest = comp && comp.seasons.length > 0 ? Math.max(...comp.seasons.map((s) => s.season)) : null;
          filters.set({ competition: v || null, season: latest, team: null });
        }}
        options={competitions.map((c) => ({
          value: c.code,
          label: c.name,
          group: c.group,
          badge: c.kind === 'tournament' ? '🏆' : undefined,
        }))}
        placeholder="All competitions"
      />

      {/* Season selector */}
      {seasons.length > 0 && (
        <Select
          label="Season"
          value={filters.season?.toString() ?? ''}
          onChange={(v) =>
            filters.set({ season: v ? Number(v) : null, team: null })
          }
          options={seasons.map((s) => ({
            value: s.season.toString(),
            label: s.label,
            badge: s.status === 'live_partial' ? '🔴' : undefined,
          }))}
          placeholder="All seasons"
        />
      )}

      {/* Team selector */}
      {filters.competition && (
        <Select
          key={`${filters.competition}-${filters.season ?? 'all'}`}
          label="Team"
          value={filters.team ?? ''}
          onChange={(v) => filters.set({ team: v || null })}
          options={uniqueTeams.map((t) => ({
            value: t.team_id,
            label: t.name,
          }))}
          placeholder={teamData ? "All teams" : "Loading clubs…"}
        />
      )}

      {/* Venue selector */}
      {showVenue && (
        <Select
          label="Venue"
          value={filters.venue ?? ''}
          onChange={(v) => filters.set({ venue: v || null })}
          options={[
            { value: 'Home', label: 'Home' },
            { value: 'Away', label: 'Away' },
          ]}
          placeholder="Any venue"
        />
      )}
    </div>
  );
}
