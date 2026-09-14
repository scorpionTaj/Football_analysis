'use client';

import { useQuery } from '@tanstack/react-query';
import { api } from '@/lib/api/client';
import { queryKeys } from '@/lib/api/query-keys';
import { useFilterParams } from '@/lib/hooks/use-filter-params';
import type { Competition } from '@/lib/api/types';

/** Shared filter bar for competition, season, team, and venue selection. */
export function FilterBar() {
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

  const competitions = catalog?.competitions ?? [];
  const selected = competitions.find((c) => c.code === filters.competition);
  const seasons = selected?.seasons ?? [];
  const teams = teamData?.teams ?? [];

  // Deduplicate teams by team_id and sort alphabetically
  const uniqueTeams = Array.from(
    new Map(teams.map((t) => [t.team_id, t])).values(),
  ).sort((a, b) => a.name.localeCompare(b.name));

  return (
    <div className="flex flex-wrap items-center gap-3">
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
          label="Team"
          value={filters.team ?? ''}
          onChange={(v) => filters.set({ team: v || null })}
          options={uniqueTeams.map((t) => ({
            value: t.team_id,
            label: t.name,
          }))}
          placeholder={uniqueTeams.length === 0 ? "Loading clubs..." : "All teams"}
        />
      )}

      {/* Venue selector */}
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
    </div>
  );
}

interface SelectOption {
  value: string;
  label: string;
  badge?: string;
}

function Select({
  label,
  value,
  onChange,
  options,
  placeholder,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  options: SelectOption[];
  placeholder: string;
}) {
  // Deduplicate options by value to guarantee unique keys and options
  const uniqueOptions = Array.from(
    new Map(options.map((opt) => [opt.value, opt])).values(),
  );

  return (
    <div className="flex flex-col gap-1">
      <label className="text-xs font-medium text-subtext0">{label}</label>
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="rounded-lg border border-surface1 bg-surface0 px-3 py-2 text-sm text-text outline-none transition-colors hover:border-surface2 focus:border-blue focus:ring-1 focus:ring-blue/30 cursor-pointer"
        aria-label={label}
      >
        <option value="">{placeholder}</option>
        {uniqueOptions.map((opt) => (
          <option key={opt.value} value={opt.value}>
            {opt.badge ? `${opt.badge} ${opt.label}` : opt.label}
          </option>
        ))}
      </select>
    </div>
  );
}
