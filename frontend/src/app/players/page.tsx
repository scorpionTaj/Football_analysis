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
import type { PlayerProfileResponse } from '@/lib/api/types';
import { FootballBadge, PlayerAvatar } from '@/lib/media-utils';
import { User, Search, ChevronRight, ChevronLeft, Download, Award } from 'lucide-react';

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

function PlayersContent() {
  const filters = useFilterParams();
  const [searchQuery, setSearchQuery] = useState(filters.get('q') || '');
  const [debouncedQuery, setDebouncedQuery] = useState(filters.get('q') || '');
  const [selectedPlayerId, setSelectedPlayerId] = useState<string | null>(filters.get('player'));
  const [currentCursor, setCurrentCursor] = useState<string | null>(null);
  const [cursorHistory, setCursorHistory] = useState<string[]>([]);

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
    cursor: currentCursor || undefined,
    limit: 10,
  }), [debouncedQuery, currentCursor]);

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
  const { data: profile, isLoading: isProfileLoading } = useQuery({
    queryKey: queryKeys.player(effectivePlayerId || ''),
    queryFn: () => api.player(effectivePlayerId || ''),
    enabled: !!effectivePlayerId,
  });

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
          <div className="relative w-full sm:w-80">
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

      {listError && (
        <ErrorMessage title="Failed to load players" detail={listError.message} retry={() => refetch()} />
      )}

      {/* Two-Pane Layout: Player List + Profile Drawer */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Left: Player Discovery List */}
        <div className="lg:col-span-5 space-y-3">
          <div className="rounded-xl border border-surface1 bg-surface0 overflow-hidden">
            <div className="p-3 border-b border-surface1 bg-mantle text-xs font-semibold text-subtext0 flex items-center justify-between">
              <span>Found {players.length} Players</span>
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
                  return (
                    <button
                      key={p.player_id}
                      onClick={() => setSelectedPlayerId(p.player_id)}
                      className={`w-full text-left p-3 flex items-center justify-between transition-colors cursor-pointer ${
                        isSelected ? 'bg-blue/15 border-l-4 border-blue' : 'hover:bg-surface1/40'
                      }`}
                    >
                      <div className="flex items-center gap-3 truncate pr-2">
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
                    <p className="text-sm text-subtext1 mt-1 flex items-center gap-2">
                      <FootballBadge url={profile.team.badge_url} name={profile.team.name} size={18} />
                      <span>{profile.team.name}</span>
                      {profile.position && (
                        <span className="rounded bg-surface1 px-2 py-0.5 text-xs text-subtext1 font-medium">
                          {profile.position}
                        </span>
                      )}
                    </p>
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
