'use client';

import { Button } from '@heroui/react';
import React, { Suspense, useMemo, useState, useEffect } from 'react';
import { useQuery, keepPreviousData } from '@tanstack/react-query';
import { api } from '@/lib/api/client';
import { toCsv } from '@/lib/csv';
import { queryKeys } from '@/lib/api/query-keys';
import { useFilterParams } from '@/lib/hooks/use-filter-params';
import { SourceBadge } from '@/components/ui/source-badge';
import { LoadingSkeleton, ErrorMessage, EmptyState } from '@/components/ui/loading';
import { PageHeader } from '@/components/ui/page-header';
import type { PlayerStat } from '@/lib/api/types';
import { User, Search, Download } from 'lucide-react';
import { Panel } from '@/components/ui/panel';
import { Select } from '@/components/ui/select';
import { Stat, StatGrid } from '@/components/ui/stat';
import { PlayerComparison, type ComparisonPlayer } from './_components/player-comparison';
import { PlayerList } from './_components/player-list';
import { PlayerProfile, formatCurrency } from './_components/player-profile';

function comparisonKey(stat: PlayerStat): string {
  return JSON.stringify([String(stat.season), stat.competition]);
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
  // The URL seeds local state; follow it when it changes without a remount (global search, back/forward).
  const urlPlayer = filters.get('player');
  const urlQuery = filters.get('q') || '';
  const [seenUrl, setSeenUrl] = useState({ player: urlPlayer, q: urlQuery });
  if (seenUrl.player !== urlPlayer || seenUrl.q !== urlQuery) {
    setSeenUrl({ player: urlPlayer, q: urlQuery });
    if (seenUrl.player !== urlPlayer) setSelectedPlayerId(urlPlayer);
    if (seenUrl.q !== urlQuery) {
      setSearchQuery(urlQuery);
      setDebouncedQuery(urlQuery);
      setCurrentCursor(null);
      setCursorHistory([]);
    }
  }

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
      p.name,
      p.team.name,
      p.position || '',
      p.nationality || '',
    ]);
    const csv = toCsv(headers, rows);
    const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `players_export.csv`;
    link.click();
    URL.revokeObjectURL(url);
  };

  const resetPaging = () => {
    setCurrentCursor(null);
    setCursorHistory([]);
  };

  return (
    <div className="space-y-4">
      <Panel bodyClassName="flex flex-col justify-between gap-3 lg:flex-row lg:items-end">
        <div className="grid w-full gap-3 sm:grid-cols-3 lg:max-w-3xl">
          <Select hideLabel label="Filter players by club" value={selectedTeam} placeholder="All clubs"
            onChange={(value) => { setSelectedTeam(value); setSelectedPosition(''); setSelectedPlayerId(null); resetPaging(); }}
            options={(playerListData?.teams || []).map((team) => ({ value: team.name, label: team.name }))} />
          <Select hideLabel label="Filter players by position" value={selectedPosition} placeholder="All positions"
            onChange={(value) => { setSelectedPosition(value); setSelectedPlayerId(null); resetPaging(); }}
            options={(playerListData?.positions || []).map((position) => ({ value: position, label: position }))} />
          <span className="relative">
            <Search className="pointer-events-none absolute left-3 top-1/2 size-3.5 -translate-y-1/2 text-overlay0" aria-hidden="true" />
            <input
              type="text"
              aria-label="Search player name"
              placeholder="Search player name..."
              value={searchQuery}
              onChange={(e) => { setSearchQuery(e.target.value); resetPaging(); }}
              className="h-9 w-full rounded-lg border border-surface1 bg-surface0 pl-9 pr-20 text-[13px] text-text placeholder:text-overlay0 focus:border-accent"
            />
            {isListFetching && <span role="status" className="absolute right-3 top-1/2 -translate-y-1/2 text-xs text-subtext0">Searching…</span>}
          </span>
        </div>
        <div className="flex items-center gap-2">
          {playerListData?.source && <SourceBadge meta={playerListData.source} />}
          <Button size="sm" variant="outline" onPress={exportCsv}>
            <Download className="size-3.5" aria-hidden="true" /> Export list
          </Button>
        </div>
      </Panel>

      <StatGrid>
        <Stat label="Players" value={(playerListData?.total_count ?? 0).toLocaleString()} />
        <Stat label="Average age" value={playerListData?.average_age ?? '—'} />
        <Stat label="Nationalities" value={playerListData?.nationality_count ?? 0} />
        <Stat label="Squad value" value={formatCurrency(playerListData?.total_market_value_eur)} />
      </StatGrid>

      {listError && <ErrorMessage title="Failed to load players" detail={listError.message} retry={() => refetch()} />}

      <PlayerComparison
        players={comparisonPlayers}
        onRemove={toggleComparisonPlayer}
        profiles={[firstComparisonProfile, secondComparisonProfile]}
        isLoading={isFirstComparisonLoading || isSecondComparisonLoading}
        error={firstComparisonError || secondComparisonError}
        retry={() => {
          if (firstComparisonError) void refetchFirstComparison();
          if (secondComparisonError) void refetchSecondComparison();
        }}
        options={comparisonOptions}
        selectedKey={selectedComparisonOption?.key || ''}
        onSelectKey={setComparisonKeySelection}
        stats={comparisonStats}
      />

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-12">
        <div className="lg:col-span-5">
          <PlayerList
            players={players}
            total={playerListData?.total_count ?? players.length}
            query={debouncedQuery}
            isLoading={isListLoading}
            selectedId={effectivePlayerId}
            onSelect={setSelectedPlayerId}
            comparison={comparisonPlayers}
            onToggleComparison={toggleComparisonPlayer}
            canGoBack={cursorHistory.length > 0}
            canGoForward={!!page?.next_cursor}
            onPrev={handlePrevPage}
            onNext={handleNextPage}
          />
        </div>
        <div className="lg:col-span-7">
          {isProfileLoading ? (
            <LoadingSkeleton lines={8} />
          ) : profileError ? (
            <ErrorMessage title="Player profile unavailable" detail={profileError.message} retry={() => refetchProfile()} />
          ) : !profile ? (
            <Panel><EmptyState icon={User} message="Select a player from the list to view profile." /></Panel>
          ) : (
            <PlayerProfile profile={profile} seasonTotals={profileSeasonTotals} />
          )}
        </div>
      </div>
    </div>
  );
}

export default function PlayersPage() {
  return (
    <div className="space-y-5">
      <PageHeader icon={User} eyebrow="Player database" title="Player Profiles & Statistics" description="Explore the open player snapshot, market values and season-by-season appearance records." />

      <Suspense fallback={<LoadingSkeleton lines={10} />}>
        <PlayersContent />
      </Suspense>
    </div>
  );
}
