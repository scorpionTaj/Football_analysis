'use client';

import { Card, Button, Chip } from '@heroui/react';
import { Suspense, useMemo, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { api } from '@/lib/api/client';
import { queryKeys } from '@/lib/api/query-keys';
import { useFilterParams } from '@/lib/hooks/use-filter-params';
import { SourceBadge } from '@/components/ui/source-badge';
import { LoadingSkeleton, ErrorMessage, EmptyState } from '@/components/ui/loading';
import { FilterBar } from '@/components/filters';
import { FootballBadge } from '@/lib/media-utils';
import { Calendar, Download, ChevronRight, ChevronLeft, Search, UserCheck } from 'lucide-react';

export function MatchesContent() {
  const filters = useFilterParams();
  const [currentCursor, setCurrentCursor] = useState<string | null>(null);
  const [cursorHistory, setCursorHistory] = useState<string[]>([]);
  const [searchQuery, setSearchQuery] = useState('');

  const queryParams = useMemo(() => ({
    competition: filters.competition || undefined,
    season: filters.season || undefined,
    team: filters.team || undefined,
    venue: filters.venue || undefined,
    cursor: currentCursor || undefined,
    limit: 20,
  }), [filters.competition, filters.season, filters.team, filters.venue, currentCursor]);

  const { data, isLoading, error, refetch } = useQuery({
    queryKey: queryKeys.matches(queryParams),
    queryFn: () => api.matches(queryParams),
  });

  const matches = data?.matches || [];
  const page = data?.page;

  // Filter matches locally by search query (team names or referee)
  const filteredMatches = useMemo(() => {
    if (!searchQuery) return matches;
    const q = searchQuery.toLowerCase();
    return matches.filter(
      (m) =>
        m.home.name.toLowerCase().includes(q) ||
        m.away.name.toLowerCase().includes(q) ||
        (m.referee && m.referee.toLowerCase().includes(q))
    );
  }, [matches, searchQuery]);

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

  const handleResetPagination = () => {
    setCurrentCursor(null);
    setCursorHistory([]);
  };

  // Quick stats computed on currently displayed matches
  const homeWins = filteredMatches.filter((m) => m.home_goals !== null && m.away_goals !== null && m.home_goals > m.away_goals).length;
  const awayWins = filteredMatches.filter((m) => m.home_goals !== null && m.away_goals !== null && m.away_goals > m.home_goals).length;
  const draws = filteredMatches.filter((m) => m.home_goals !== null && m.away_goals !== null && m.home_goals === m.away_goals).length;

  // Export CSV handler
  const exportCsv = () => {
    const headers = ['Date', 'Competition', 'Season', 'Home Team', 'Home Goals', 'Away Goals', 'Away Team', 'Referee'];
    const rows = filteredMatches.map((m) => [
      m.match_date,
      m.competition,
      m.season,
      `"${m.home.name}"`,
      m.home_goals ?? '',
      m.away_goals ?? '',
      `"${m.away.name}"`,
      `"${m.referee || ''}"`,
    ]);
    const csvContent = [headers.join(','), ...rows.map((r) => r.join(','))].join('\n');
    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `matches_export.csv`;
    link.click();
    URL.revokeObjectURL(url);
  };

  if (isLoading) return <LoadingSkeleton lines={10} />;
  if (error) {
    return <ErrorMessage title="Failed to load matches" detail={error.message} retry={() => refetch()} />;
  }

  return (
    <div className="space-y-6">
      {/* Global Filter Bar */}
      <Card className="rounded-xl bg-surface0 border border-surface1 p-4 space-y-3 shadow-sm">
        <div className="flex flex-wrap items-center justify-between gap-3 border-b border-surface1 pb-3">
          <FilterBar />
          {data?.source && <SourceBadge meta={data.source} />}
        </div>

        {/* Secondary search and action bar */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pt-1">
          <div className="relative w-full sm:w-72">
            <Search className="absolute left-3 top-2.5 h-3.5 w-3.5 text-overlay0" />
            <input
              type="text"
              placeholder="Search club or referee..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full rounded-lg border border-surface1 bg-mantle pl-9 pr-3 py-1.5 text-xs text-text outline-none focus:border-blue"
            />
          </div>

          <div className="flex items-center gap-2">
            {currentCursor && (
              <Button
                size="sm"
                variant="outline"
                onPress={handleResetPagination}
                className="px-2.5 py-1 text-xs cursor-pointer"
              >
                Back to First Page
              </Button>
            )}
            <Button
              size="sm"
              variant="outline"
              onPress={exportCsv}
              className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium cursor-pointer"
            >
              <Download className="h-3.5 w-3.5 text-blue" />
              <span>Export CSV</span>
            </Button>
          </div>
        </div>
      </Card>

      {/* KPI Stats for current page */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
        <Card className="rounded-xl bg-surface0 border border-surface1 p-4 shadow-sm">
          <p className="text-xs text-subtext0 uppercase font-medium">Matches on Page</p>
          <p className="text-2xl font-bold text-text mt-1">{filteredMatches.length}</p>
        </Card>
        <Card className="rounded-xl bg-surface0 border border-surface1 p-4 shadow-sm">
          <p className="text-xs text-subtext0 uppercase font-medium">Home Wins</p>
          <p className="text-2xl font-bold text-blue mt-1">
            {homeWins} <span className="text-xs text-subtext0 font-normal">({matches.length > 0 ? ((homeWins / matches.length) * 100).toFixed(0) : 0}%)</span>
          </p>
        </Card>
        <Card className="rounded-xl bg-surface0 border border-surface1 p-4 shadow-sm">
          <p className="text-xs text-subtext0 uppercase font-medium">Draws</p>
          <p className="text-2xl font-bold text-yellow mt-1">
            {draws} <span className="text-xs text-subtext0 font-normal">({matches.length > 0 ? ((draws / matches.length) * 100).toFixed(0) : 0}%)</span>
          </p>
        </Card>
        <Card className="rounded-xl bg-surface0 border border-surface1 p-4 shadow-sm">
          <p className="text-xs text-subtext0 uppercase font-medium">Away Wins</p>
          <p className="text-2xl font-bold text-peach mt-1">
            {awayWins} <span className="text-xs text-subtext0 font-normal">({matches.length > 0 ? ((awayWins / matches.length) * 100).toFixed(0) : 0}%)</span>
          </p>
        </Card>
      </div>

      {/* Match Cards */}
      {filteredMatches.length === 0 ? (
        <EmptyState icon="📅" message="No matches match the filter parameters." suggestion="Try clearing or broadening the filter selection." />
      ) : (
        <div className="space-y-2.5">
          {filteredMatches.map((m, idx) => (
            <div
              key={`${m.match_date}_${m.home.team_id}_${m.away.team_id}_${idx}`}
              className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 p-4 rounded-xl bg-surface0 border border-surface1 hover:border-surface2 transition-colors"
            >
              {/* Date & Competition */}
              <div className="flex items-center gap-2.5 text-xs text-subtext0 min-w-[140px]">
                <span className="font-mono text-overlay1">{m.match_date}</span>
                <span className="rounded bg-surface1 px-2 py-0.5 text-subtext1 font-medium text-[11px]">
                  {m.competition}
                </span>
              </div>

              {/* Match Scoreline */}
              <div className="flex items-center justify-center gap-3 sm:gap-6 flex-1 px-4">
                <div className="w-1/2 flex items-center justify-end gap-2 font-semibold text-text truncate">
                  <span className="truncate">{m.home.name}</span>
                  <FootballBadge url={m.home.badge_url} name={m.home.name} size={22} />
                </div>
                <div className="flex items-center justify-center min-w-[64px]">
                  <span className="rounded-md bg-mantle border border-surface1 px-3 py-1 text-sm font-bold text-blue tracking-wider">
                    {m.home_goals !== null ? m.home_goals : '-'} : {m.away_goals !== null ? m.away_goals : '-'}
                  </span>
                </div>
                <div className="w-1/2 flex items-center justify-start gap-2 font-semibold text-text truncate">
                  <FootballBadge url={m.away.badge_url} name={m.away.name} size={22} />
                  <span className="truncate">{m.away.name}</span>
                </div>
              </div>

              {/* Referee & Venue */}
              <div className="flex items-center justify-end gap-3 text-xs text-subtext0 min-w-[160px]">
                {m.referee && (
                  <span className="flex items-center gap-1 text-overlay1 truncate" title={`Referee: ${m.referee}`}>
                    <UserCheck className="h-3 w-3 text-overlay0" />
                    {m.referee}
                  </span>
                )}
                {m.venue && (
                  <span className="text-overlay0 text-[11px] hidden md:inline">
                    {m.venue}
                  </span>
                )}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Pagination Footer */}
      <div className="flex items-center justify-between pt-2 border-t border-surface1 text-xs text-subtext0">
        <div>
          Showing {filteredMatches.length} matches (limit {page?.limit || 10})
        </div>

        <div className="flex items-center gap-2">
          <Button
            size="sm"
            variant="outline"
            isDisabled={cursorHistory.length === 0}
            onPress={handlePrevPage}
            className="flex items-center gap-1 px-3 py-1.5 text-xs font-medium cursor-pointer"
          >
            <ChevronLeft className="h-3.5 w-3.5" />
            <span>Previous</span>
          </Button>

          <Button
            size="sm"
            variant="outline"
            isDisabled={!page?.next_cursor}
            onPress={handleNextPage}
            className="flex items-center gap-1 px-3 py-1.5 text-xs font-medium cursor-pointer"
          >
            <span>Next</span>
            <ChevronRight className="h-3.5 w-3.5" />
          </Button>
        </div>
      </div>
    </div>
  );
}

export default function MatchesPage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-text tracking-tight">Match Explorer</h1>
        <p className="text-sm text-subtext0 mt-1">
          Paginated fixture results across domestic leagues and tournaments with cursor progression and referee details.
        </p>
      </div>

      <Suspense fallback={<LoadingSkeleton lines={10} />}>
        <MatchesContent />
      </Suspense>
    </div>
  );
}
