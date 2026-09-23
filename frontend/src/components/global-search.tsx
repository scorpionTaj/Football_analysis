'use client';

import Link from 'next/link';
import { Input } from '@heroui/react';
import { useQuery } from '@tanstack/react-query';
import { Search } from 'lucide-react';
import { useEffect, useMemo, useState } from 'react';
import { api } from '@/lib/api/client';
import { queryKeys } from '@/lib/api/query-keys';
import { fuzzySort } from '@/lib/fuzzy';

export function GlobalSearch({ onNavigate }: { onNavigate?: () => void }) {
  const [query, setQuery] = useState('');
  const [debounced, setDebounced] = useState('');
  useEffect(() => {
    const timer = window.setTimeout(() => setDebounced(query.trim()), 250);
    return () => window.clearTimeout(timer);
  }, [query]);

  const { data: catalog, isLoading: catalogLoading } = useQuery({ queryKey: queryKeys.catalog, queryFn: api.catalog });
  const { data: teams, isLoading: teamsLoading } = useQuery({ queryKey: queryKeys.teams(), queryFn: () => api.teams() });
  const { data: players, isFetching: playersFetching } = useQuery({
    queryKey: queryKeys.players({ q: debounced, limit: 5 }),
    queryFn: () => api.players({ q: debounced, limit: 5 }),
    enabled: debounced.length >= 2,
  });

  const results = useMemo(() => {
    if (debounced.length < 2) return [];
    const clubMap = new Map((teams?.teams || []).map((team) => [team.team_id, team]));
    const competitions = fuzzySort(debounced, catalog?.competitions || [], (competition) => `${competition.name} ${competition.code}`)
      .slice(0, 3)
      .map((competition) => ({
        key: `competition-${competition.code}`,
        label: competition.name,
        meta: 'Competition',
        href: competition.kind === 'tournament'
          ? `/tournaments?competition=${competition.code}&season=${competition.seasons.at(-1)?.season || ''}`
          : `/tables?competition=${competition.code}&season=${competition.seasons.at(-1)?.season || ''}`,
      }));
    const clubs = fuzzySort(debounced, Array.from(clubMap.values()), (team) => team.name)
      .slice(0, 5)
      .map((team) => ({
        key: `club-${team.team_id}`,
        label: team.name,
        meta: 'Club / nation',
        href: `/clubs?team=${encodeURIComponent(team.name)}`,
      }));
    const playerRows = (players?.players || []).map((player) => ({
      key: `player-${player.player_id}`,
      label: player.name,
      meta: player.team.name,
      href: `/players?q=${encodeURIComponent(player.name)}&player=${encodeURIComponent(player.player_id)}`,
    }));
    return [...competitions, ...clubs, ...playerRows].slice(0, 8);
  }, [catalog, debounced, players, teams]);

  return (
    <div className="relative px-3 py-3">
      <div className="relative">
        <Search className="pointer-events-none absolute left-3 top-1/2 z-10 size-4 -translate-y-1/2 text-overlay0" aria-hidden="true" />
        <Input
          aria-label="Search clubs, players and competitions"
          placeholder="Search platform…"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          className="pl-9"
        />
      </div>
      {debounced.length >= 2 ? (
        <div className="absolute inset-x-3 top-[3.8rem] z-20 overflow-hidden rounded-xl border border-surface1 bg-mantle shadow-2xl">
          {results.length ? results.map((result) => (
            <Link
              key={result.key}
              href={result.href}
              onClick={() => { setQuery(''); onNavigate?.(); }}
              className="flex items-center justify-between gap-3 border-b border-surface1/60 px-3 py-2.5 text-xs last:border-0 hover:bg-surface0"
            >
              <span className="truncate font-semibold text-text">{result.label}</span>
              <span className="shrink-0 text-[10px] text-subtext0">{result.meta}</span>
            </Link>
          )) : <p role="status" className="px-3 py-3 text-xs text-subtext0">
            {catalogLoading || teamsLoading || playersFetching ? 'Searching…' : 'No matching data.'}
          </p>}
        </div>
      ) : null}
    </div>
  );
}
