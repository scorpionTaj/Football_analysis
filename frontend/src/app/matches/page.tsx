'use client';

import { Card, Button } from '@heroui/react';
import { Suspense, useEffect, useMemo, useState } from 'react';
import { keepPreviousData, useQuery } from '@tanstack/react-query';
import { api } from '@/lib/api/client';
import { queryKeys } from '@/lib/api/query-keys';
import { useFilterParams } from '@/lib/hooks/use-filter-params';
import { SourceBadge } from '@/components/ui/source-badge';
import { LoadingSkeleton, ErrorMessage, EmptyState } from '@/components/ui/loading';
import { PageHeader } from '@/components/ui/page-header';
import { FilterBar } from '@/components/filters';
import { FootballBadge } from '@/lib/media-utils';
import { Calendar, Download, ChevronRight, ChevronLeft, Search, UserCheck } from 'lucide-react';
import type { Match } from '@/lib/api/types';
import { MatchDetailCentre } from '@/components/match-detail-centre';

function MatchesContent() {
  const filters = useFilterParams();
  const [currentCursor, setCurrentCursor] = useState<string | null>(null);
  const [cursorHistory, setCursorHistory] = useState<string[]>([]);
  const [searchQuery, setSearchQuery] = useState('');
  const [debouncedSearch, setDebouncedSearch] = useState('');
  const matchDate = filters.get('match_date');
  const matchHome = filters.get('home');
  const matchAway = filters.get('away');

  useEffect(() => {
    const timer = window.setTimeout(() => {
      setDebouncedSearch(searchQuery.trim());
      setCurrentCursor(null);
      setCursorHistory([]);
    }, 350);
    return () => window.clearTimeout(timer);
  }, [searchQuery]);

  const queryParams = useMemo(() => ({
    competition: filters.competition || undefined,
    season: filters.season || undefined,
    team: filters.team || undefined,
    venue: filters.venue || undefined,
    q: debouncedSearch || undefined,
    cursor: currentCursor || undefined,
    limit: 20,
  }), [filters.competition, filters.season, filters.team, filters.venue, debouncedSearch, currentCursor]);

  const { data, isLoading, isFetching, isPlaceholderData, error, refetch } = useQuery({
    queryKey: queryKeys.matches(queryParams),
    queryFn: () => api.matches(queryParams),
    placeholderData: keepPreviousData,
  });

  const selectedMatchParams = matchDate && matchHome && matchAway && filters.competition && filters.season ? {
    competition: filters.competition,
    season: filters.season,
    match_date: matchDate,
    home: matchHome,
    away: matchAway,
  } : null;
  const { data: detail, isLoading: isDetailLoading, error: detailError, refetch: refetchDetail } = useQuery({
    queryKey: queryKeys.matchDetail(selectedMatchParams || {}),
    queryFn: () => api.matchDetail(selectedMatchParams!),
    enabled: Boolean(selectedMatchParams),
  });

  const matches = useMemo(() => data?.matches || [], [data?.matches]);
  const page = data?.page;

  const filteredMatches = matches;

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

  const openMatchCentre = (match: Match) => {
    filters.set({
      competition: match.competition,
      season: match.season,
      match_date: match.match_date,
      home: match.home.name,
      away: match.away.name,
    });
    window.scrollTo({ top: 0, behavior: 'smooth' });
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

  if (selectedMatchParams) {
    if (isDetailLoading) return <LoadingSkeleton lines={10} />;
    if (detailError) return <ErrorMessage title="Match detail could not load" detail={detailError.message} retry={() => refetchDetail()} />;
    if (detail) return <MatchDetailCentre detail={detail} onBack={() => filters.set({ match_date: null, home: null, away: null })} />;
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
              aria-label="Search matches by club or referee"
              placeholder="Search club or referee..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full rounded-lg border border-surface1 bg-mantle pl-9 pr-20 py-1.5 text-xs text-text outline-none focus:border-blue"
            />
            {isFetching && <span role="status" className="absolute right-3 top-2 text-[10px] text-blue">Searching…</span>}
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
            {homeWins} <span className="text-xs text-subtext0 font-normal">({filteredMatches.length > 0 ? ((homeWins / filteredMatches.length) * 100).toFixed(0) : 0}%)</span>
          </p>
        </Card>
        <Card className="rounded-xl bg-surface0 border border-surface1 p-4 shadow-sm">
          <p className="text-xs text-subtext0 uppercase font-medium">Draws</p>
          <p className="text-2xl font-bold text-yellow mt-1">
            {draws} <span className="text-xs text-subtext0 font-normal">({filteredMatches.length > 0 ? ((draws / filteredMatches.length) * 100).toFixed(0) : 0}%)</span>
          </p>
        </Card>
        <Card className="rounded-xl bg-surface0 border border-surface1 p-4 shadow-sm">
          <p className="text-xs text-subtext0 uppercase font-medium">Away Wins</p>
          <p className="text-2xl font-bold text-peach mt-1">
            {awayWins} <span className="text-xs text-subtext0 font-normal">({filteredMatches.length > 0 ? ((awayWins / filteredMatches.length) * 100).toFixed(0) : 0}%)</span>
          </p>
        </Card>
      </div>

      {/* Match Cards */}
      {error ? (
        <ErrorMessage title="Failed to load matches" detail={error.message} retry={() => refetch()} />
      ) : isLoading ? (
        <LoadingSkeleton lines={6} />
      ) : filteredMatches.length === 0 && !isPlaceholderData ? (
        <EmptyState icon="📅" message="No matches match the filter parameters." suggestion="Try clearing or broadening the filter selection." />
      ) : (
        <div className="space-y-2.5">
          {filteredMatches.map((m, idx) => (
            <button
              type="button"
              key={`${m.match_date}_${m.home.team_id}_${m.away.team_id}_${idx}`}
              onClick={() => openMatchCentre(m)}
              className="flex w-full cursor-pointer flex-col gap-3 rounded-xl border border-surface1 bg-surface0 p-4 text-left transition-colors hover:border-blue/60 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue sm:flex-row sm:items-center sm:justify-between"
              aria-label={`Open ${m.home.name} versus ${m.away.name} match centre`}
            >
              {/* Date & Competition */}
              <div className="flex items-center gap-2.5 text-xs text-subtext0 min-w-[140px]">
                <span className="font-mono text-overlay1">{m.match_date}{m.kickoff_time ? ` · ${m.kickoff_time} source time` : ''}</span>
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
                {m.home_shots !== null && m.away_shots !== null ? (
                  <span className="rounded-lg bg-mantle px-2 py-1 font-mono text-[11px] text-subtext1" title="Shots (home–away)">
                    Shots {m.home_shots}–{m.away_shots}
                  </span>
                ) : null}
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
                <ChevronRight className="size-4 shrink-0 text-blue" aria-hidden="true" />
              </div>
            </button>
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
            isDisabled={isFetching || !page?.next_cursor}
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
      <PageHeader icon={Calendar} eyebrow="Fixtures and results" title="Match Centre" description="Open any result for its factual match story, technical plan, verified lineup roles, timeline and statistics." />

      <Suspense fallback={<LoadingSkeleton lines={10} />}>
        <MatchesContent />
      </Suspense>
    </div>
  );
}
