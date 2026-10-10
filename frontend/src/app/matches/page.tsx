'use client';

import { Button } from '@heroui/react';
import { Suspense, useEffect, useMemo, useState } from 'react';
import { keepPreviousData, useQuery } from '@tanstack/react-query';
import { api } from '@/lib/api/client';
import { toCsv } from '@/lib/csv';
import { queryKeys } from '@/lib/api/query-keys';
import { useFilterParams } from '@/lib/hooks/use-filter-params';
import { SourceBadge } from '@/components/ui/source-badge';
import { LoadingSkeleton, ErrorMessage, EmptyState } from '@/components/ui/loading';
import { PageHeader } from '@/components/ui/page-header';
import { Panel } from '@/components/ui/panel';
import { Stat, StatGrid } from '@/components/ui/stat';
import { Chip } from '@/components/ui/chip';
import { FilterBar } from '@/components/filters';
import { FootballBadge } from '@/lib/media-utils';
import { ArrowLeft, Calendar, Download, ChevronRight, ChevronLeft, Search, UserCheck } from 'lucide-react';
import type { Match } from '@/lib/api/types';
import { MatchDetailCentre } from '@/components/match-detail-centre';

function MatchesContent() {
  const filters = useFilterParams();
  const [searchQuery, setSearchQuery] = useState('');
  const [debouncedSearch, setDebouncedSearch] = useState('');
  // A cursor only means something for the filters that produced it. A filter change is a
  // router.push that may or may not remount this page, so reset explicitly (during render).
  const pagingKey = [filters.competition, filters.season, filters.team, filters.venue, debouncedSearch].join('|');
  const [paging, setPaging] = useState({ key: pagingKey, cursor: null as string | null, history: [] as string[] });
  if (paging.key !== pagingKey) setPaging({ key: pagingKey, cursor: null, history: [] });
  const currentCursor = paging.key === pagingKey ? paging.cursor : null;
  const cursorHistory = paging.key === pagingKey ? paging.history : [];
  const matchDate = filters.get('match_date');
  const matchHome = filters.get('home');
  const matchAway = filters.get('away');

  useEffect(() => {
    const timer = window.setTimeout(() => {
      setDebouncedSearch(searchQuery.trim());
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
    const next = page?.next_cursor;
    if (next) setPaging({ key: pagingKey, cursor: next, history: [...cursorHistory, currentCursor || ''] });
  };

  const handlePrevPage = () => {
    if (cursorHistory.length > 0) {
      setPaging({ key: pagingKey, cursor: cursorHistory[cursorHistory.length - 1] || null, history: cursorHistory.slice(0, -1) });
    }
  };

  const handleResetPagination = () => setPaging({ key: pagingKey, cursor: null, history: [] });

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
      m.home.name,
      m.home_goals ?? '',
      m.away_goals ?? '',
      m.away.name,
      m.referee || '',
    ]);
    const csvContent = toCsv(headers, rows);
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
    if (detailError) return <div className="space-y-4">
      <Button variant="outline" size="sm" onPress={() => filters.set({ match_date: null, home: null, away: null })} className="gap-2"><ArrowLeft className="size-4" />Back to matches</Button>
      <ErrorMessage title="Match detail could not load" detail={detailError.message} retry={() => refetchDetail()} />
    </div>;
    if (detail) return <MatchDetailCentre detail={detail} onBack={() => filters.set({ match_date: null, home: null, away: null })} />;
  }

  const share = (count: number) => `${filteredMatches.length ? Math.round((count / filteredMatches.length) * 100) : 0}% of this page`;
  const dateGroups = filteredMatches.reduce<{ date: string; matches: Match[] }[]>((groups, match) => {
    const last = groups.at(-1);
    if (last && last.date === match.match_date) last.matches.push(match);
    else groups.push({ date: match.match_date, matches: [match] });
    return groups;
  }, []);

  return (
    <div className="space-y-4">
      <Panel bodyClassName="space-y-3">
        <div className="flex flex-wrap items-end justify-between gap-3">
          <FilterBar />
          {data?.source && <SourceBadge meta={data.source} />}
        </div>
        <div className="flex flex-col justify-between gap-3 border-t border-surface1 pt-3 sm:flex-row sm:items-center">
          <div className="relative w-full sm:w-80">
            <Search className="pointer-events-none absolute left-3 top-1/2 size-3.5 -translate-y-1/2 text-overlay0" aria-hidden="true" />
            <input
              type="text"
              aria-label="Search matches by club or referee"
              placeholder="Search club or referee..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="h-9 w-full rounded-lg border border-surface1 bg-surface0 pl-9 pr-20 text-[13px] text-text placeholder:text-overlay0 focus:border-accent"
            />
            {isFetching && <span role="status" className="absolute right-3 top-1/2 -translate-y-1/2 text-xs text-subtext0">Searching…</span>}
          </div>
          <div className="flex items-center gap-2">
            {currentCursor && (
              <Button size="sm" variant="ghost" onPress={handleResetPagination}>Back to first page</Button>
            )}
            <Button size="sm" variant="outline" onPress={exportCsv}>
              <Download className="size-3.5" aria-hidden="true" /> Export CSV
            </Button>
          </div>
        </div>
      </Panel>

      <p className="text-xs text-subtext0 sm:hidden">{filteredMatches.length} {filteredMatches.length === 1 ? 'fixture' : 'fixtures'} on this page</p>
      <StatGrid className="hidden sm:grid">
        <Stat label="Matches on page" value={filteredMatches.length} />
        <Stat label="Home wins" value={homeWins} hint={share(homeWins)} />
        <Stat label="Draws" value={draws} hint={share(draws)} />
        <Stat label="Away wins" value={awayWins} hint={share(awayWins)} />
      </StatGrid>

      {error ? (
        <ErrorMessage title="Failed to load matches" detail={error.message} retry={() => refetch()} />
      ) : isLoading ? (
        <LoadingSkeleton lines={6} />
      ) : filteredMatches.length === 0 && !isPlaceholderData ? (
        <Panel><EmptyState icon={Calendar} message="No matches match the filter parameters." suggestion="Try clearing or broadening the filter selection." /></Panel>
      ) : (
        <div className="overflow-hidden rounded-xl border border-surface1 bg-surface0">
          {dateGroups.map((group) => (
            <section key={group.date} aria-label={group.date}>
              <h2 className="sticky top-14 z-[1] border-b border-surface1 bg-mantle px-4 py-1.5 text-xs font-medium tabular-nums text-subtext0 lg:top-0">{group.date}</h2>
              <ul>
                {group.matches.map((m, idx) => (
                  <li key={`${m.match_date}_${m.home.team_id}_${m.away.team_id}_${idx}`} className="border-b border-surface1 last:border-b-0">
                    <button
                      type="button"
                      onClick={() => openMatchCentre(m)}
                      className="grid w-full grid-cols-1 gap-2 px-4 py-2.5 text-left transition-colors hover:bg-surface1/40 lg:grid-cols-[7rem_minmax(0,1fr)_12rem] lg:items-center"
                      aria-label={`Open ${m.home.name} versus ${m.away.name} match centre`}
                    >
                      <span className="flex items-center gap-2 text-xs text-subtext0">
                        <span className="tabular-nums">{m.kickoff_time || '—'}</span>
                        <Chip>{m.competition}</Chip>
                      </span>
                      <span className="grid min-w-0 grid-cols-[minmax(0,1fr)_auto_minmax(0,1fr)] items-center gap-3">
                        <span className="flex min-w-0 flex-col items-center gap-1 text-center text-[13px] font-medium leading-tight text-text sm:flex-row-reverse sm:justify-start sm:gap-2 sm:text-right">
                          <FootballBadge url={m.home.badge_url} name={m.home.name} size={20} />
                          <span className="min-w-0 [overflow-wrap:anywhere]">{m.home.name}</span>
                        </span>
                        <span className={`min-w-14 rounded-md px-2 py-0.5 text-center text-sm font-semibold tabular-nums ${m.home_goals === null ? 'text-subtext0' : 'bg-mantle text-text'}`}>
                          {m.home_goals !== null ? m.home_goals : '–'} : {m.away_goals !== null ? m.away_goals : '–'}
                        </span>
                        <span className="flex min-w-0 flex-col items-center gap-1 text-center text-[13px] font-medium leading-tight text-text sm:flex-row sm:justify-start sm:gap-2 sm:text-left">
                          <FootballBadge url={m.away.badge_url} name={m.away.name} size={20} />
                          <span className="min-w-0 [overflow-wrap:anywhere]">{m.away.name}</span>
                        </span>
                      </span>
                      <span className="flex min-w-0 items-center justify-end gap-3 text-xs text-subtext0">
                        {m.home_shots !== null && m.away_shots !== null ? (
                          <span className="tabular-nums" title="Shots (home–away)">Shots {m.home_shots}–{m.away_shots}</span>
                        ) : null}
                        {m.referee && (
                          <span className="flex min-w-0 items-center gap-1 truncate" title={`Referee: ${m.referee}`}>
                            <UserCheck className="size-3 shrink-0 text-overlay0" aria-hidden="true" />
                            <span className="truncate">{m.referee}</span>
                          </span>
                        )}
                        <ChevronRight className="size-4 shrink-0 text-overlay0" aria-hidden="true" />
                      </span>
                    </button>
                  </li>
                ))}
              </ul>
            </section>
          ))}
        </div>
      )}

      <div className="flex items-center justify-between text-xs text-subtext0">
        <span className="tabular-nums">Showing {filteredMatches.length} matches (limit {page?.limit || 10})</span>
        <div className="flex items-center gap-2">
          <Button size="sm" variant="outline" isDisabled={cursorHistory.length === 0} onPress={handlePrevPage}>
            <ChevronLeft className="size-3.5" aria-hidden="true" />
            <span>Previous</span>
          </Button>
          <Button size="sm" variant="outline" isDisabled={isFetching || !page?.next_cursor} onPress={handleNextPage}>
            <span>Next</span>
            <ChevronRight className="size-3.5" aria-hidden="true" />
          </Button>
        </div>
      </div>
    </div>
  );
}

export default function MatchesPage() {
  return (
    <div className="space-y-5">
      <PageHeader icon={Calendar} eyebrow="Fixtures and results" title="Match Centre" description="Open any result for its factual match story, technical plan, verified lineup roles, timeline and statistics." />

      <Suspense fallback={<LoadingSkeleton lines={10} />}>
        <MatchesContent />
      </Suspense>
    </div>
  );
}
