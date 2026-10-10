'use client';

import { Button } from '@heroui/react';
import { Suspense, useCallback, useMemo, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { api } from '@/lib/api/client';
import { toCsv } from '@/lib/csv';
import { queryKeys } from '@/lib/api/query-keys';
import { useFilterParams } from '@/lib/hooks/use-filter-params';
import type { Match } from '@/lib/api/types';
import { SourceBadge } from '@/components/ui/source-badge';
import { LoadingSkeleton, ErrorMessage } from '@/components/ui/loading';
import { PageHeader } from '@/components/ui/page-header';
import { Shield, Download } from 'lucide-react';
import { usePagination } from '@/components/ui/pagination';
import { FootballBadge } from '@/lib/media-utils';
import { Panel } from '@/components/ui/panel';
import { Select } from '@/components/ui/select';
import { Segmented } from '@/components/ui/segmented';
import { Stat, StatGrid } from '@/components/ui/stat';
import { fromClubSide, seasonLabel, summarize } from './_lib';
import { useTableView } from '@/lib/hooks/use-table-view';
import { RANKING_COLUMNS } from '@/lib/table-columns';
import { ClubCharts } from './_components/club-charts';
import { SeasonTable } from './_components/season-table';
import { MatchLog } from './_components/match-log';
import { HeadToHead } from './_components/head-to-head';

function ClubLabContent() {
  const filters = useFilterParams();
  const selectedClub = filters.team || 'Arsenal';
  const [activeTab, setActiveTab] = useState<'profile' | 'h2h'>('profile');
  const [opponentClub, setOpponentClub] = useState<string>('Chelsea');
  const [formWindow, setFormWindow] = useState(5);

  // Fetch all teams to populate the club selector
  const { data: teamData } = useQuery({
    queryKey: queryKeys.teams(),
    queryFn: () => api.teams(),
  });

  const allTeams = useMemo(() => {
    const map = new Map<string, NonNullable<typeof teamData>['teams'][number]>();
    for (const t of teamData?.teams || []) {
      const key = t.team_id || t.name;
      const existing = map.get(key);
      if (
        !existing
        || t.played > existing.played
        || (t.played === existing.played && !existing.badge_url && !!t.badge_url)
      ) {
        map.set(key, t);
      }
    }
    return Array.from(map.values()).sort((a, b) => a.name.localeCompare(b.name));
  }, [teamData]);
  const selectedTeam = allTeams.find((team) => team.name === selectedClub);
  const opponentTeam = allTeams.find((team) => team.name === opponentClub);
  const selectedTeamId = selectedTeam?.team_id;
  // Until the team list resolves the id, fall back to the name so home/away are not all read as away.
  const isClubHome = useCallback(
    (match: Match) => (selectedTeamId ? match.home.team_id === selectedTeamId : match.home.name === selectedClub),
    [selectedTeamId, selectedClub],
  );

  // Request analysis for the selected club across all seasons
  const requestBody = useMemo(() => ({
    competitions: [],
    seasons: [],
    teams: [selectedClub],
    venue: null,
    form_window: formWindow,
  }), [selectedClub, formWindow]);

  const { data: analysis, isLoading: isAnalysisLoading, error: analysisError, refetch } = useQuery({
    queryKey: queryKeys.analysis(requestBody),
    queryFn: () => api.analysis(requestBody),
    enabled: !!selectedClub,
  });

  // Request analysis for opponent club (for Head-to-Head)
  const opponentRequestBody = useMemo(() => ({
    competitions: [],
    seasons: [],
    teams: [opponentClub],
    venue: null,
    form_window: 5,
  }), [opponentClub]);

  const { data: opponentAnalysis } = useQuery({
    queryKey: queryKeys.analysis(opponentRequestBody),
    queryFn: () => api.analysis(opponentRequestBody),
    enabled: activeTab === 'h2h' && !!opponentClub,
  });

  // Fetch recent matches for the club
  const { data: matchData, isLoading: isMatchesLoading, error: matchesError, refetch: refetchMatches } = useQuery({
    queryKey: queryKeys.matches({ team: selectedClub, limit: 100 }),
    queryFn: () => api.matches({ team: selectedClub, limit: 100 }),
    enabled: !!selectedClub,
  });

  // Direct filtering spans leagues and cups without losing older meetings to
  // either club's general recent-match pagination.
  const { data: h2hData, isLoading: isH2HLoading, error: h2hError, refetch: refetchH2H } = useQuery({
    queryKey: queryKeys.matches({ team: selectedClub, opponent: opponentClub, limit: 200 }),
    queryFn: () => api.matches({ team: selectedClub, opponent: opponentClub, limit: 200 }),
    enabled: activeTab === 'h2h' && !!selectedClub && !!opponentClub,
  });

  const seasonsList = useMemo(() => {
    return [...(analysis?.rankings || [])].sort((a, b) => a.season - b.season);
  }, [analysis]);

  const benchmarkRequest = useMemo(() => ({
    competitions: Array.from(new Set(seasonsList.map((row) => row.competition))),
    seasons: Array.from(new Set(seasonsList.map((row) => row.season))),
    teams: [],
    venue: null,
    form_window: formWindow,
  }), [seasonsList, formWindow]);

  const { data: benchmark } = useQuery({
    queryKey: queryKeys.analysis(benchmarkRequest),
    queryFn: () => api.analysis(benchmarkRequest),
    enabled: benchmarkRequest.competitions.length > 0,
  });

  // Paginated season history table (10 per page)
  const seasonTable = useTableView(seasonsList, { columns: RANKING_COLUMNS, initial: { key: 'season', dir: 'desc' } });
  const { paginatedItems: paginatedSeasons, paginationControls: SeasonsPagination } = usePagination(seasonTable.rows, 10);

  const totals = useMemo(() => summarize(seasonsList), [seasonsList]);
  const opponentTotals = useMemo(() => summarize(opponentAnalysis?.rankings || []), [opponentAnalysis?.rankings]);

  // Evolution chart data
  const chartData = useMemo(() => {
    return seasonsList.map((s) => ({
      season: seasonLabel(s.season),
      Points: s.points,
      GoalsScored: s.goals_for,
      GoalsConceded: s.goals_against,
    }));
  }, [seasonsList]);

  const matches = useMemo(() => matchData?.matches || [], [matchData?.matches]);
  const rollingForm = useMemo(() => {
    const ordered = [...matches].filter((match) => match.home_goals != null && match.away_goals != null).sort((a, b) => a.match_date.localeCompare(b.match_date));
    const points: number[] = ordered.map((match) => {
      const isHome = isClubHome(match);
      const goalsFor = isHome ? match.home_goals! : match.away_goals!;
      const goalsAgainst = isHome ? match.away_goals! : match.home_goals!;
      return goalsFor > goalsAgainst ? 3 : goalsFor === goalsAgainst ? 1 : 0;
    });
    return ordered.map((match, index) => {
      const window = points.slice(Math.max(0, index - formWindow + 1), index + 1);
      return { date: match.match_date, PPG: Number((window.reduce((sum, value) => sum + value, 0) / window.length).toFixed(2)) };
    });
  }, [matches, isClubHome, formWindow]);

  const percentileProfile = useMemo(() => {
    const rows = benchmark?.rankings || [];
    const own = rows.filter((row) => row.team.name === selectedClub);
    const metrics = [
      ['Scoring', 'goals_per_game'], ['Points', 'points_per_game'],
      ['Win rate', 'win_rate'], ['Clean sheets', 'clean_sheet_rate'],
    ] as const;
    return metrics.map(([label, key]) => {
      const ownValue = own.length ? own.reduce((sum, row) => sum + row[key], 0) / own.length : 0;
      const values = rows.map((row) => row[key]);
      const percentile = values.length ? 100 * values.filter((value) => value <= ownValue).length / values.length : 0;
      return { label, percentile: Number(percentile.toFixed(0)) };
    });
  }, [benchmark?.rankings, selectedClub]);
  // Paginated club recent fixtures (10 per page)
  const { paginatedItems: paginatedMatches, paginationControls: MatchesPagination } = usePagination(matches, 10);

  // Head-to-Head matches calculation
  const h2hMatches = useMemo(() => {
    // The API has already resolved provider aliases (for example Arsenal and
    // Arsenal FC), so keep every direct result instead of re-filtering on the
    // presentation label.
    const combined = h2hData?.matches || [];
    const seen = new Set<string>();
    const unique: typeof combined = [];
    for (const m of combined) {
      const key = `${m.match_date}_${m.home.name}_${m.away.name}`;
      if (!seen.has(key)) {
        seen.add(key);
        unique.push(m);
      }
    }
    return unique.sort((a, b) => b.match_date.localeCompare(a.match_date));
  }, [h2hData?.matches]);

  // Paginated Head-to-Head encounters (10 per page)
  const { paginatedItems: paginatedH2HMatches, paginationControls: H2HPagination } = usePagination(h2hMatches, 10);

  const h2hStats = useMemo(() => {
    const stats = { clashes: h2hMatches.length, clubAWins: 0, clubBWins: 0, draws: 0, clubAGoals: 0, clubBGoals: 0 };
    for (const m of h2hMatches) {
      const { own, other, result } = fromClubSide(m, isClubHome(m));
      if (result === null) continue;
      stats.clubAGoals += own!;
      stats.clubBGoals += other!;
      if (result === 'W') stats.clubAWins++;
      else if (result === 'L') stats.clubBWins++;
      else stats.draws++;
    }
    return stats;
  }, [h2hMatches, isClubHome]);

  // Export CSV
  const exportCsv = () => {
    const headers = ['Season', 'Competition', 'Played', 'W', 'D', 'L', 'GF', 'GA', 'GD', 'Points', 'PPG', 'Win Rate %', 'Clean Sheet %'];
    const rows = seasonsList.map((s) => [
      `${s.season}/${s.season + 1}`,
      s.competition,
      s.played,
      s.wins,
      s.draws,
      s.losses,
      s.goals_for,
      s.goals_against,
      s.goal_difference,
      s.points,
      s.points_per_game.toFixed(2),
      s.win_rate.toFixed(1),
      s.clean_sheet_rate.toFixed(1),
    ]);
    const csv = toCsv(headers, rows);
    const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `${selectedClub}_performance_history.csv`;
    link.click();
    URL.revokeObjectURL(url);
  };

  if (isAnalysisLoading) return <LoadingSkeleton lines={10} />;
  if (analysisError) {
    return <ErrorMessage title="Failed to load club analysis" detail={analysisError.message} retry={() => refetch()} />;
  }

  const teamOptions = allTeams.map((team) => ({ value: team.name, label: team.name }));

  return (
    <div className="space-y-4">
      <Panel bodyClassName="flex flex-col justify-between gap-4 lg:flex-row lg:items-end">
        <div className="flex flex-wrap items-end gap-3">
          <FootballBadge name={selectedClub} url={selectedTeam?.badge_url} size={36} />
          <Select label="Primary club" value={selectedClub} onChange={(value) => filters.set({ team: value })} options={teamOptions} className="w-52" />
          {activeTab === 'h2h' && (
            <Select label="Opponent club" value={opponentClub} onChange={setOpponentClub} options={teamOptions} className="w-52" />
          )}
          <Select label="Recent form window" value={String(formWindow)} onChange={(value) => setFormWindow(Number(value))}
            options={[3, 5, 8, 10].map((value) => ({ value: String(value), label: `Last ${value}` }))} className="w-32" />
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Segmented label="Club view" value={activeTab} onChange={setActiveTab}
            options={[{ value: 'profile', label: 'Club profile' }, { value: 'h2h', label: 'Head-to-head' }]} />
          {analysis?.source && <SourceBadge meta={analysis.source} />}
          <Button size="sm" variant="outline" onPress={exportCsv}>
            <Download className="size-3.5" aria-hidden="true" /> Export
          </Button>
        </div>
      </Panel>

      {activeTab === 'profile' ? (
        <>
          <StatGrid>
            <Stat label="Matches (all seasons)" value={totals.played} />
            <Stat label="Win rate" value={`${totals.winRate}%`} />
            <Stat label="Total points" value={totals.points} />
            <Stat label="Points per game" value={totals.ppg} />
          </StatGrid>
          <ClubCharts club={selectedClub} trajectory={chartData} rollingForm={rollingForm} formWindow={formWindow} percentiles={percentileProfile} />
          <SeasonTable seasons={paginatedSeasons} pagination={SeasonsPagination} sortProps={seasonTable.sortProps} />
          <MatchLog matches={paginatedMatches} isClubHome={isClubHome} isLoading={isMatchesLoading}
            error={matchesError} retry={() => refetchMatches()} pagination={MatchesPagination} />
        </>
      ) : (
        <HeadToHead
          a={{ name: selectedClub, badge: selectedTeam?.badge_url, totals }}
          b={{ name: opponentClub, badge: opponentTeam?.badge_url, totals: opponentTotals }}
          stats={h2hStats}
          matches={paginatedH2HMatches}
          isClubHome={isClubHome}
          isLoading={isH2HLoading}
          error={h2hError}
          retry={() => refetchH2H()}
          pagination={H2HPagination}
        />
      )}
    </div>
  );
}

export default function ClubsPage() {
  return (
    <div className="space-y-5">
      <PageHeader icon={Shield} eyebrow="Club intelligence" title="Club Lab & Head-to-Head" description="Profile long-term performance, inspect recent results and compare two clubs across leagues and cups." />

      <Suspense fallback={<LoadingSkeleton lines={10} />}>
        <ClubLabContent />
      </Suspense>
    </div>
  );
}
