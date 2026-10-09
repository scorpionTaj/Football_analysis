'use client';

import { Card, Chip, Button } from '@heroui/react';
import React, { Suspense, useMemo, useState, useEffect } from 'react';
import { useQuery, keepPreviousData } from '@tanstack/react-query';
import { api } from '@/lib/api/client';
import { queryKeys } from '@/lib/api/query-keys';
import { useFilterParams } from '@/lib/hooks/use-filter-params';
import { SourceBadge } from '@/components/ui/source-badge';
import { LoadingSkeleton, ErrorMessage, EmptyState } from '@/components/ui/loading';
import { PageHeader } from '@/components/ui/page-header';
import { usePagination } from '@/components/ui/pagination';
import type { PlayerProfileResponse, PlayerStat } from '@/lib/api/types';
import { FootballBadge, PlayerAvatar } from '@/lib/media-utils';
import { User, Search, ChevronRight, ChevronLeft, Download, Award } from 'lucide-react';
import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';

function formatCurrency(eur: number | null | undefined): string {
  if (!eur) return 'N/A';
  if (eur >= 1_000_000) {
    return `€${(eur / 1_000_000).toFixed(1)}M`;
  }
  if (eur >= 1_000) {
    return `€${(eur / 1_000).toFixed(0)}k`;
  }
  return `€${eur.toLocaleString()}`;
}

type ComparisonPlayer = { id: string; name: string };

function comparisonKey(stat: PlayerStat): string {
  return JSON.stringify([String(stat.season), stat.competition]);
}

function formatComparisonValue(value: number | null | undefined): string {
  return value == null ? '—' : value.toLocaleString();
}

function formatPer90(value: number | null | undefined, minutes: number | null | undefined): string {
  return value == null || minutes == null || minutes <= 0 ? '—' : (value * 90 / minutes).toFixed(2);
}

function PlayersContent() {
  const filters = useFilterParams();
  const [searchQuery, setSearchQuery] = useState(filters.get('q') || '');
  const [debouncedQuery, setDebouncedQuery] = useState(filters.get('q') || '');
  const [selectedPlayerId, setSelectedPlayerId] = useState<string | null>(filters.get('player'));
  const [selectedTeam, setSelectedTeam] = useState('');
  const [selectedPosition, setSelectedPosition] = useState('');
  const [currentCursor, setCurrentCursor] = useState<string | null>(null);
  const [cursorHistory, setCursorHistory] = useState<string[]>([]);
  const [comparisonPlayers, setComparisonPlayers] = useState<[ComparisonPlayer | null, ComparisonPlayer | null]>([null, null]);
  const [comparisonKeySelection, setComparisonKeySelection] = useState('');

  // 300ms debounce to prevent constant refetching on each keystroke
  useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedQuery(searchQuery);
    }, 300);
    return () => clearTimeout(timer);
  }, [searchQuery]);

  // Fetch players list
  const listParams = useMemo(() => ({
    q: debouncedQuery || undefined,
    team: selectedTeam || undefined,
    position: selectedPosition || undefined,
    cursor: currentCursor || undefined,
    limit: 10,
  }), [debouncedQuery, selectedTeam, selectedPosition, currentCursor]);

  const { data: playerListData, isLoading: isListLoading, isFetching: isListFetching, error: listError, refetch } = useQuery({
    queryKey: queryKeys.players(listParams),
    queryFn: () => api.players(listParams),
    placeholderData: keepPreviousData,
  });

  const players = playerListData?.players || [];
  const page = playerListData?.page;

  // Auto-select the first player if none selected
  const effectivePlayerId = selectedPlayerId || (players.length > 0 ? players[0].player_id : null);

  // Fetch selected player profile
  const { data: profile, isLoading: isProfileLoading, error: profileError, refetch: refetchProfile } = useQuery({
    queryKey: queryKeys.player(effectivePlayerId || ''),
    queryFn: () => api.player(effectivePlayerId || ''),
    enabled: !!effectivePlayerId,
  });

  const { data: firstComparisonProfile, isLoading: isFirstComparisonLoading, error: firstComparisonError, refetch: refetchFirstComparison } = useQuery({
    queryKey: queryKeys.player(comparisonPlayers[0]?.id || ''),
    queryFn: () => api.player(comparisonPlayers[0]?.id || ''),
    enabled: !!comparisonPlayers[0],
  });
  const { data: secondComparisonProfile, isLoading: isSecondComparisonLoading, error: secondComparisonError, refetch: refetchSecondComparison } = useQuery({
    queryKey: queryKeys.player(comparisonPlayers[1]?.id || ''),
    queryFn: () => api.player(comparisonPlayers[1]?.id || ''),
    enabled: !!comparisonPlayers[1],
  });

  const comparisonOptions = useMemo(() => {
    const pairs = new Map<string, { key: string; season: string; competition: string | null }>();
    for (const stat of [...(firstComparisonProfile?.stats || []), ...(secondComparisonProfile?.stats || [])]) {
      if (stat.statistic !== 'season' || stat.season == null) continue;
      const key = comparisonKey(stat);
      pairs.set(key, { key, season: String(stat.season), competition: stat.competition });
    }
    return [...pairs.values()].sort((a, b) =>
      b.season.localeCompare(a.season, undefined, { numeric: true }) ||
      (a.competition || '').localeCompare(b.competition || ''),
    );
  }, [firstComparisonProfile?.stats, secondComparisonProfile?.stats]);

  const firstComparisonKeys = new Set((firstComparisonProfile?.stats || [])
    .filter((stat) => stat.statistic === 'season' && stat.season != null)
    .map(comparisonKey));
  const secondComparisonKeys = new Set((secondComparisonProfile?.stats || [])
    .filter((stat) => stat.statistic === 'season' && stat.season != null)
    .map(comparisonKey));
  const defaultComparisonOption = comparisonOptions.find((option) =>
    firstComparisonKeys.has(option.key) && secondComparisonKeys.has(option.key),
  ) || comparisonOptions[0];
  const selectedComparisonOption = comparisonOptions.find((option) => option.key === comparisonKeySelection) || defaultComparisonOption;
  const comparisonStats = [firstComparisonProfile, secondComparisonProfile].map((player) =>
    player?.stats.find((stat) => stat.statistic === 'season' && stat.season != null && comparisonKey(stat) === selectedComparisonOption?.key),
  );

  const toggleComparisonPlayer = (player: ComparisonPlayer) => {
    setComparisonPlayers(([first, second]) => {
      if (first?.id === player.id) return [second, null];
      if (second?.id === player.id) return [first, null];
      return [first || player, first ? player : null];
    });
  };

  const profileSeasonTotals = useMemo(() => {
    const totals = new Map<string, { season: string; appearances: number; goals: number; assists: number; minutes: number }>();
    for (const row of profile?.stats || []) {
      const season = String(row.season ?? 'Unknown');
      const item = totals.get(season) || { season, appearances: 0, goals: 0, assists: 0, minutes: 0 };
      item.appearances += row.appearances ?? 0;
      item.goals += row.goals ?? 0;
      item.assists += row.assists ?? 0;
      item.minutes += row.minutes_played ?? 0;
      totals.set(season, item);
    }
    return Array.from(totals.values()).sort((a, b) => a.season.localeCompare(b.season));
  }, [profile?.stats]);

  const profileTotals = useMemo(() => profileSeasonTotals.reduce((acc, row) => ({
    appearances: acc.appearances + row.appearances,
    goals: acc.goals + row.goals,
    assists: acc.assists + row.assists,
    minutes: acc.minutes + row.minutes,
  }), { appearances: 0, goals: 0, assists: 0, minutes: 0 }), [profileSeasonTotals]);

  const handleNextPage = () => {
    if (page?.next_cursor) {
      setCursorHistory((prev) => [...prev, currentCursor || '']);
      setCurrentCursor(page.next_cursor);
    }
  };

  const handlePrevPage = () => {
    if (cursorHistory.length > 0) {
      const prev = cursorHistory[cursorHistory.length - 1];
      setCursorHistory((prevList) => prevList.slice(0, -1));
      setCurrentCursor(prev || null);
    }
  };

  // CSV Export of current player list
  const exportCsv = () => {
    const headers = ['ID', 'Player', 'Team', 'Position', 'Nationality'];
    const rows = players.map((p) => [
      p.player_id,
      `"${p.name}"`,
      `"${p.team.name}"`,
      `"${p.position || ''}"`,
      `"${p.nationality || ''}"`,
    ]);
    const csv = [headers.join(','), ...rows.map((r) => r.join(','))].join('\n');
    const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `players_export.csv`;
    link.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="space-y-6">
      {/* Search Header - persistently mounted, never unmounts */}
      <Card className="p-4 rounded-xl bg-surface0 border border-surface1 shadow-sm">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div className="grid w-full gap-3 sm:grid-cols-3 lg:max-w-3xl">
            <select
              value={selectedTeam}
              onChange={(event) => {
                setSelectedTeam(event.target.value);
                setSelectedPosition('');
                setSelectedPlayerId(null);
                setCurrentCursor(null);
                setCursorHistory([]);
              }}
              className="rounded-lg border border-surface1 bg-mantle px-3 py-2 text-xs text-text outline-none focus:border-blue"
              aria-label="Filter players by club"
            >
              <option value="">All clubs</option>
              {(playerListData?.teams || []).map((team) => <option key={team.team_id} value={team.name}>{team.name}</option>)}
            </select>
            <select
              value={selectedPosition}
              onChange={(event) => {
                setSelectedPosition(event.target.value);
                setSelectedPlayerId(null);
                setCurrentCursor(null);
                setCursorHistory([]);
              }}
              className="rounded-lg border border-surface1 bg-mantle px-3 py-2 text-xs text-text outline-none focus:border-blue"
              aria-label="Filter players by position"
            >
              <option value="">All positions</option>
              {(playerListData?.positions || []).map((position) => <option key={position} value={position}>{position}</option>)}
            </select>
            <div className="relative">
            <Search className="absolute left-3 top-3 h-4 w-4 text-overlay0 pointer-events-none" />
            <input
              type="text"
              placeholder="Search player name..."
              value={searchQuery}
              onChange={(e) => {
                setSearchQuery(e.target.value);
                setCurrentCursor(null);
                setCursorHistory([]);
              }}
              className="w-full rounded-lg border border-surface1 bg-mantle pl-9 pr-3 py-2 text-xs text-text outline-none focus:border-blue placeholder:text-overlay0 transition-colors"
            />
            {isListFetching && (
              <span className="absolute right-3 top-3 text-[10px] text-blue font-medium animate-pulse">
                Searching...
              </span>
            )}
            </div>
          </div>

          <div className="flex items-center gap-3">
            {playerListData?.source && <SourceBadge meta={playerListData.source} />}
            <Button
              size="sm"
              variant="outline"
              onPress={exportCsv}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium cursor-pointer"
            >
              <Download className="h-3.5 w-3.5 text-blue" />
              <span>Export List</span>
            </Button>
          </div>
        </div>
      </Card>

      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        {[
          ['Players', playerListData?.total_count ?? 0],
          ['Average age', playerListData?.average_age ?? '—'],
          ['Nationalities', playerListData?.nationality_count ?? 0],
          ['Squad value', formatCurrency(playerListData?.total_market_value_eur)],
        ].map(([label, value]) => <Card key={String(label)} className="rounded-xl border border-surface1 bg-surface0 p-4"><p className="text-xs uppercase text-subtext0">{label}</p><p className="mt-1 text-xl font-bold text-text">{value}</p></Card>)}
      </div>

      {listError && (
        <ErrorMessage title="Failed to load players" detail={listError.message} retry={() => refetch()} />
      )}

      <section aria-label="Player comparison" className="rounded-xl border border-surface1 bg-surface0 p-4 sm:p-5 space-y-4">
        <div>
          <h2 className="text-lg font-bold text-text">Compare players</h2>
          <p className="text-xs text-subtext0 mt-1">Transfermarkt Open Dataset · 2025/26 snapshot, through July 2026. These are historical records, not current 2026/27 squads. Choosing a third player replaces Player 2.</p>
        </div>
        <div className="grid gap-3 sm:grid-cols-2">
          {comparisonPlayers.map((player, index) => (
            <div key={index} className="flex items-center justify-between gap-3 rounded-lg border border-surface1 bg-mantle p-3">
              <div className="min-w-0">
                <p className="text-xs text-subtext0">Player {index + 1}</p>
                <p className="truncate text-sm font-semibold text-text">{player?.name || 'Choose from the list below'}</p>
              </div>
              {player && <button type="button" onClick={() => toggleComparisonPlayer(player)} aria-label={`Remove ${player.name} from comparison`} className="shrink-0 rounded px-2 py-1 text-xs text-blue hover:bg-surface1 focus-visible:outline focus-visible:outline-2 focus-visible:outline-blue">Remove</button>}
            </div>
          ))}
        </div>
        {comparisonPlayers[0] && comparisonPlayers[1] && (
          isFirstComparisonLoading || isSecondComparisonLoading ? <LoadingSkeleton lines={4} /> :
          firstComparisonError || secondComparisonError ? (
            <ErrorMessage title="Failed to load comparison" detail={(firstComparisonError || secondComparisonError)?.message || 'Try again.'} retry={() => {
              if (firstComparisonError) void refetchFirstComparison();
              if (secondComparisonError) void refetchSecondComparison();
            }} />
          ) : firstComparisonProfile && secondComparisonProfile ? (
            comparisonOptions.length ? (
              <div className="space-y-3">
                <div className="flex flex-col gap-1 sm:max-w-sm">
                  <label htmlFor="comparison-season-competition" className="text-xs font-medium text-subtext1">Season and competition</label>
                  <select id="comparison-season-competition" value={selectedComparisonOption?.key || ''} onChange={(event) => setComparisonKeySelection(event.target.value)} className="rounded-lg border border-surface1 bg-mantle px-3 py-2 text-sm text-text outline-none focus:border-blue">
                    {comparisonOptions.map((option) => <option key={option.key} value={option.key}>{option.season} · {option.competition || 'Unspecified competition'}</option>)}
                  </select>
                </div>
                <div className="overflow-x-auto rounded-lg border border-surface1">
                  <table className="w-full min-w-[300px] text-sm">
                    <caption className="sr-only">Historical season statistics for {firstComparisonProfile.name} and {secondComparisonProfile.name}</caption>
                    <thead className="bg-mantle text-xs text-subtext0"><tr><th scope="col" className="p-2 text-left">Metric</th><th scope="col" className="p-2 text-right">Player 1</th><th scope="col" className="p-2 text-right">Player 2</th></tr></thead>
                    <tbody className="divide-y divide-surface1 text-text">
                      {([
                        ['Appearances', comparisonStats[0]?.appearances, comparisonStats[1]?.appearances],
                        ['Goals', comparisonStats[0]?.goals, comparisonStats[1]?.goals],
                        ['Assists', comparisonStats[0]?.assists, comparisonStats[1]?.assists],
                        ['Minutes', comparisonStats[0]?.minutes_played, comparisonStats[1]?.minutes_played],
                      ] as const).map(([label, first, second]) => <tr key={label}><th scope="row" className="p-2 text-left font-medium">{label}</th><td className="p-2 text-right tabular-nums">{formatComparisonValue(first)}</td><td className="p-2 text-right tabular-nums">{formatComparisonValue(second)}</td></tr>)}
                      <tr><th scope="row" className="p-2 text-left font-medium">Goals / 90</th><td className="p-2 text-right tabular-nums">{formatPer90(comparisonStats[0]?.goals, comparisonStats[0]?.minutes_played)}</td><td className="p-2 text-right tabular-nums">{formatPer90(comparisonStats[1]?.goals, comparisonStats[1]?.minutes_played)}</td></tr>
                      <tr><th scope="row" className="p-2 text-left font-medium">Assists / 90</th><td className="p-2 text-right tabular-nums">{formatPer90(comparisonStats[0]?.assists, comparisonStats[0]?.minutes_played)}</td><td className="p-2 text-right tabular-nums">{formatPer90(comparisonStats[1]?.assists, comparisonStats[1]?.minutes_played)}</td></tr>
                    </tbody>
                  </table>
                </div>
                <p className="text-xs text-subtext0">— means unavailable. Per-90 figures require recorded minutes above zero.</p>
              </div>
            ) : <p className="text-sm text-subtext0">No historical season statistics are available for these players.</p>
          ) : null
        )}
      </section>

      {/* Two-Pane Layout: Player List + Profile Drawer */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Left: Player Discovery List */}
        <div className="lg:col-span-5 space-y-3">
          <div className="rounded-xl border border-surface1 bg-surface0 overflow-hidden">
            <div className="p-3 border-b border-surface1 bg-mantle text-xs font-semibold text-subtext0 flex items-center justify-between">
              <span>Found {playerListData?.total_count ?? players.length} Players</span>
              {debouncedQuery && (
                <Chip size="sm" variant="soft" color="accent" className="text-[10px]">
                  Matching &quot;{debouncedQuery}&quot;
                </Chip>
              )}
            </div>

            {isListLoading && players.length === 0 ? (
              <div className="p-4">
                <LoadingSkeleton lines={6} />
              </div>
            ) : players.length === 0 ? (
              <div className="p-8 text-center">
                <EmptyState icon="👤" message="No players found." suggestion="Try another spelling or clear search." />
              </div>
            ) : (
              <div className="divide-y divide-surface1 max-h-[640px] overflow-y-auto">
                {players.map((p) => {
                  const isSelected = effectivePlayerId === p.player_id;
                  const comparisonSlot = comparisonPlayers.findIndex((player) => player?.id === p.player_id);
                  return (
                    <div key={p.player_id} className={`flex items-center transition-colors ${
                        isSelected ? 'bg-blue/15 border-l-4 border-blue' : 'hover:bg-surface1/40'
                      }`}>
                      <button type="button" aria-label={`View profile for ${p.name}`} aria-pressed={isSelected} onClick={() => setSelectedPlayerId(p.player_id)} className="flex min-w-0 flex-1 cursor-pointer items-center justify-between p-3 text-left focus-visible:outline focus-visible:outline-2 focus-visible:outline-blue">
                      <div className="flex items-center gap-3 min-w-0 truncate pr-2">
                        <PlayerAvatar image_url={p.image_url} name={p.name} size={36} />
                        <div className="space-y-0.5 truncate">
                          <p className={`font-semibold text-sm truncate ${isSelected ? 'text-blue' : 'text-text'}`}>
                            {p.name}
                          </p>
                          <div className="flex items-center gap-2 text-xs text-subtext0">
                            <span className="truncate">{p.team.name}</span>
                            {p.position && (
                              <>
                                <span>·</span>
                                <span className="rounded bg-surface1 px-1.5 py-0.2 text-[11px] text-subtext1">
                                  {p.position}
                                </span>
                              </>
                            )}
                          </div>
                        </div>
                      </div>
                      <ChevronRight className={`h-4 w-4 shrink-0 ${isSelected ? 'text-blue' : 'text-overlay0'}`} />
                      </button>
                      <button type="button" aria-label={`${comparisonSlot >= 0 ? 'Remove' : 'Add'} ${p.name} ${comparisonSlot >= 0 ? 'from' : 'to'} comparison`} aria-pressed={comparisonSlot >= 0} onClick={() => toggleComparisonPlayer({ id: p.player_id, name: p.name })} className="mr-3 shrink-0 rounded-lg border border-surface1 px-2 py-1 text-xs font-medium text-blue hover:bg-surface1 focus-visible:outline focus-visible:outline-2 focus-visible:outline-blue">
                        {comparisonSlot >= 0 ? `Player ${comparisonSlot + 1}` : 'Compare'}
                      </button>
                    </div>
                  );
                })}
              </div>
            )}

            {/* Pagination Controls */}
            <div className="flex items-center justify-between p-3 border-t border-surface1 bg-mantle text-xs text-subtext0">
              <Button
                size="sm"
                variant="outline"
                isDisabled={cursorHistory.length === 0}
                onPress={handlePrevPage}
                className="flex items-center gap-1 px-2.5 py-1 text-xs cursor-pointer"
              >
                <ChevronLeft className="h-3 w-3" />
                <span>Prev</span>
              </Button>
              <span className="font-medium text-[11px]">{players.length} items</span>
              <Button
                size="sm"
                variant="outline"
                isDisabled={!page?.next_cursor}
                onPress={handleNextPage}
                className="flex items-center gap-1 px-2.5 py-1 text-xs cursor-pointer"
              >
                <span>Next</span>
                <ChevronRight className="h-3 w-3" />
              </Button>
            </div>
          </div>
        </div>

        {/* Right: Selected Player Profile */}
        <div className="lg:col-span-7">
          {isProfileLoading ? (
            <LoadingSkeleton lines={8} />
          ) : profileError ? (
            <ErrorMessage title="Player profile unavailable" detail={profileError.message} retry={() => refetchProfile()} />
          ) : !profile ? (
            <div className="rounded-xl border border-surface1 bg-surface0 p-12 text-center">
              <p className="text-subtext0">Select a player from the list to view profile.</p>
            </div>
          ) : (
            <div className="rounded-xl border border-surface1 bg-surface0 p-6 space-y-6">
              {/* Profile Card Header */}
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-surface1 pb-5">
                <div className="flex items-center gap-4">
                  <PlayerAvatar
                    image_url={profile.image_url}
                    name={profile.name}
                    size={64}
                    className="rounded-2xl"
                  />
                  <div>
                    <h2 className="text-xl font-bold text-text">{profile.name}</h2>
                    <div className="text-sm text-subtext1 mt-1 flex items-center gap-2">
                      <FootballBadge url={profile.team.badge_url} name={profile.team.name} size={18} />
                      <span>{profile.team.name}</span>
                      {profile.position && (
                        <span className="rounded bg-surface1 px-2 py-0.5 text-xs text-subtext1 font-medium">
                          {profile.position}
                        </span>
                      )}
                    </div>
                  </div>
                </div>

                <div className="flex flex-col items-start sm:items-end">
                  <span className="text-xs text-subtext0 uppercase font-medium">Market Value</span>
                  <span className="text-2xl font-bold text-green mt-0.5">
                    {formatCurrency(profile.market_value_eur)}
                  </span>
                </div>
              </div>

              {/* Bio Details Grid */}
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                <div className="rounded-lg bg-mantle p-3 border border-surface1">
                  <p className="text-xs text-subtext0">Nationality</p>
                  <p className="text-sm font-semibold text-text mt-0.5">{profile.nationality || 'N/A'}</p>
                </div>
                <div className="rounded-lg bg-mantle p-3 border border-surface1">
                  <p className="text-xs text-subtext0">Date of Birth</p>
                  <p className="text-sm font-semibold text-text mt-0.5">{profile.date_born || 'N/A'}</p>
                </div>
                <div className="rounded-lg bg-mantle p-3 border border-surface1">
                  <p className="text-xs text-subtext0">Height</p>
                  <p className="text-sm font-semibold text-text mt-0.5">{profile.height_cm ? `${profile.height_cm} cm` : 'N/A'}</p>
                </div>
                <div className="rounded-lg bg-mantle p-3 border border-surface1">
                  <p className="text-xs text-subtext0">Preferred Foot</p>
                  <p className="text-sm font-semibold text-text capitalize mt-0.5">{profile.foot || 'N/A'}</p>
                </div>
              </div>

              {/* Historical Career Statistics */}
              <div className="space-y-3">
                <h3 className="text-sm font-bold text-text uppercase tracking-wider flex items-center gap-2">
                  <Award className="h-4 w-4 text-yellow" /> Season Statistics History
                </h3>
                <PlayerStatsTable stats={profile.stats} />
              </div>

              {profileSeasonTotals.length ? (
                <div className="space-y-4 border-t border-surface1 pt-5">
                  <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
                    {[
                      ['Appearances', profileTotals.appearances], ['Goals', profileTotals.goals],
                      ['Assists', profileTotals.assists], ['Minutes', profileTotals.minutes.toLocaleString()],
                    ].map(([label, value]) => <div key={String(label)} className="rounded-lg border border-surface1 bg-mantle p-3"><p className="text-xs text-subtext0">{label}</p><p className="mt-1 text-lg font-bold text-text">{value}</p></div>)}
                  </div>
                  <div className="h-64">
                    <ResponsiveContainer width="100%" height="100%">
                      <BarChart data={profileSeasonTotals} margin={{ top: 8, right: 8, left: -18, bottom: 0 }}>
                        <CartesianGrid strokeDasharray="3 3" stroke="#313244" />
                        <XAxis dataKey="season" stroke="#7f849c" fontSize={11} />
                        <YAxis stroke="#7f849c" fontSize={11} />
                        <Tooltip contentStyle={{ backgroundColor: '#181825', borderColor: '#45475a', borderRadius: 8 }} />
                        <Legend />
                        <Bar dataKey="goals" fill="#cba6f7" radius={[4, 4, 0, 0]} />
                        <Bar dataKey="assists" fill="#89b4fa" radius={[4, 4, 0, 0]} />
                      </BarChart>
                    </ResponsiveContainer>
                  </div>
                </div>
              ) : null}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function PlayerStatsTable({ stats }: { stats: PlayerProfileResponse['stats'] }) {
  const { paginatedItems, PaginationComponent } = usePagination(stats, 10);

  if (stats.length === 0) {
    return <p className="text-xs text-subtext0 py-4">No historical competition stats recorded for this profile.</p>;
  }

  return (
    <div className="space-y-3">
      <div className="rounded-lg border border-surface1 overflow-hidden">
        <table className="w-full text-left text-xs">
          <thead className="border-b border-surface1 bg-mantle text-subtext0 uppercase">
            <tr>
              <th className="py-2.5 px-3">Season</th>
              <th className="py-2.5 px-3">Competition</th>
              <th className="py-2.5 px-2 text-center">Apps</th>
              <th className="py-2.5 px-2 text-center text-green">Goals</th>
              <th className="py-2.5 px-2 text-center text-blue">Assists</th>
              <th className="py-2.5 px-2 text-right">Mins</th>
              <th className="py-2.5 px-2 text-center text-yellow">Yel</th>
              <th className="py-2.5 px-2 text-center text-red">Red</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-surface1">
            {paginatedItems.map((st, i) => (
              <tr key={i} className="hover:bg-surface1/30">
                <td className="py-2 px-3 font-mono font-medium text-text">{st.season}</td>
                <td className="py-2 px-3 text-subtext1 capitalize">{st.competition || 'domestic'}</td>
                <td className="py-2 px-2 text-center">{st.appearances ?? '-'}</td>
                <td className="py-2 px-2 text-center font-bold text-green">{st.goals ?? 0}</td>
                <td className="py-2 px-2 text-center font-bold text-blue">{st.assists ?? 0}</td>
                <td className="py-2 px-2 text-right font-mono text-subtext0">{st.minutes_played?.toLocaleString() ?? '-'}</td>
                <td className="py-2 px-2 text-center text-yellow">{st.yellow_cards ?? 0}</td>
                <td className="py-2 px-2 text-center text-red">{st.red_cards ?? 0}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <PaginationComponent />
    </div>
  );
}

export default function PlayersPage() {
  return (
    <div className="space-y-6">
      <PageHeader icon={User} eyebrow="Player database" title="Player Profiles & Statistics" description="Explore the open player snapshot, market values and season-by-season appearance records." />

      <Suspense fallback={<LoadingSkeleton lines={10} />}>
        <PlayersContent />
      </Suspense>
    </div>
  );
}
