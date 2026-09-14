'use client';

import { Card, Button } from '@heroui/react';
import { Suspense, useMemo, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { api } from '@/lib/api/client';
import { queryKeys } from '@/lib/api/query-keys';
import { useFilterParams } from '@/lib/hooks/use-filter-params';
import { SourceBadge } from '@/components/ui/source-badge';
import { LoadingSkeleton, ErrorMessage, EmptyState } from '@/components/ui/loading';
import { PageHeader } from '@/components/ui/page-header';
import { usePagination } from '@/components/ui/pagination';
import { Table as TableIcon, Download } from 'lucide-react';
import { FootballBadge, CompetitionBadge } from '@/lib/media-utils';

function LeagueTablesContent() {
  const filters = useFilterParams();
  const selectedCompetition = filters.competition || 'E0';
  const [venueFilter, setVenueFilter] = useState<'All' | 'Home' | 'Away'>('All');

  const { data: catalog } = useQuery({
    queryKey: queryKeys.catalog,
    queryFn: () => api.catalog(),
  });

  const compOptions = catalog?.competitions.filter((c) => c.kind === 'domestic') || [];
  const currentComp = compOptions.find((c) => c.code === selectedCompetition);
  const seasons = currentComp?.seasons || [];
  const latestSeason = seasons.length > 0 ? Math.max(...seasons.map((s) => s.season)) : 2026;
  const selectedSeason = filters.season || latestSeason;

  const requestBody = useMemo(() => ({
    competitions: [selectedCompetition],
    seasons: [selectedSeason],
    teams: [],
    venue: venueFilter === 'All' ? null : venueFilter,
    form_window: 5,
  }), [selectedCompetition, selectedSeason, venueFilter]);

  const { data: analysis, isLoading, error, refetch } = useQuery({
    queryKey: queryKeys.analysis(requestBody),
    queryFn: () => api.analysis(requestBody),
  });

  const rankings = analysis?.rankings || [];
  const { paginatedItems: paginatedRankings, PaginationComponent: TablePagination } = usePagination(rankings, 10);

  // Export CSV
  const exportCsv = () => {
    const headers = ['Pos', 'Team', 'P', 'W', 'D', 'L', 'GF', 'GA', 'GD', 'Pts', 'PPG', 'Form'];
    const rows = rankings.map((r) => [
      r.rank,
      `"${r.team.name}"`,
      r.played,
      r.wins,
      r.draws,
      r.losses,
      r.goals_for,
      r.goals_against,
      r.goal_difference,
      r.points,
      r.points_per_game.toFixed(2),
      `"${r.form || ''}"`,
    ]);
    const csv = [headers.join(','), ...rows.map((r) => r.join(','))].join('\n');
    const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `${selectedCompetition}_${selectedSeason}_table.csv`;
    link.click();
    URL.revokeObjectURL(url);
  };

  if (isLoading) return <LoadingSkeleton lines={10} />;
  if (error) {
    return <ErrorMessage title="Failed to load league table" detail={error.message} retry={() => refetch()} />;
  }

  const totalGoals = rankings.reduce((acc, r) => acc + r.goals_for, 0);
  const totalMatches = analysis?.match_count || (rankings.reduce((acc, r) => acc + r.played, 0) / 2);
  const avgGoals = totalMatches > 0 ? (totalGoals / totalMatches).toFixed(2) : '0';

  return (
    <div className="space-y-6">
      {/* Controls Bar */}
      <Card className="p-4 rounded-xl bg-surface0 border border-surface1 shadow-sm">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div className="flex flex-wrap items-center gap-4">
            <CompetitionBadge
              code={selectedCompetition}
              name={currentComp?.name || selectedCompetition}
              badge_url={currentComp?.badge_url}
              size={40}
            />
            <div className="flex flex-wrap items-center gap-3">
              {/* League */}
              <div className="flex flex-col gap-1">
                <label className="text-xs font-medium text-subtext0">League</label>
                <select
                  value={selectedCompetition}
                  onChange={(e) => filters.set({ competition: e.target.value })}
                  className="rounded-lg border border-surface1 bg-mantle px-3 py-1.5 text-xs font-medium text-text outline-none cursor-pointer hover:border-surface2"
                >
                  {compOptions.map((c) => (
                    <option key={c.code} value={c.code}>{c.name}</option>
                  ))}
                </select>
              </div>

              {/* Season */}
              <div className="flex flex-col gap-1">
                <label className="text-xs font-medium text-subtext0">Season</label>
                <select
                  value={selectedSeason}
                  onChange={(e) => filters.set({ season: Number(e.target.value) })}
                  className="rounded-lg border border-surface1 bg-mantle px-3 py-1.5 text-xs font-medium text-text outline-none cursor-pointer hover:border-surface2"
                >
                  {seasons.map((s) => (
                    <option key={s.season} value={s.season}>{s.label}</option>
                  ))}
                </select>
              </div>

              {/* Venue */}
              <div className="flex flex-col gap-1">
                <label className="text-xs font-medium text-subtext0">Venue</label>
                <div className="flex rounded-lg bg-mantle border border-surface1 p-0.5">
                  {(['All', 'Home', 'Away'] as const).map((v) => (
                    <Button
                      key={v}
                      size="sm"
                      variant={venueFilter === v ? 'primary' : 'ghost'}
                      onPress={() => setVenueFilter(v)}
                      className={`px-3 py-1 text-xs font-medium min-w-0 h-7 cursor-pointer`}
                    >
                      {v}
                    </Button>
                  ))}
                </div>
              </div>
            </div>
          </div>

          <div className="flex items-center gap-3">
            {analysis?.source && <SourceBadge meta={analysis.source} />}
            <Button
              size="sm"
              variant="outline"
              onPress={exportCsv}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium cursor-pointer"
            >
              <Download className="h-3.5 w-3.5 text-blue" />
              <span>Export CSV</span>
            </Button>
          </div>
        </div>
      </Card>

      {/* KPI Stats */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
        <Card className="rounded-xl bg-surface0 border border-surface1 p-4 shadow-sm">
          <p className="text-xs text-subtext0 uppercase font-medium">Clubs</p>
          <p className="text-2xl font-bold text-text mt-1">{rankings.length}</p>
        </Card>
        <Card className="rounded-xl bg-surface0 border border-surface1 p-4 shadow-sm">
          <p className="text-xs text-subtext0 uppercase font-medium">Matches Played</p>
          <p className="text-2xl font-bold text-blue mt-1">{totalMatches}</p>
        </Card>
        <Card className="rounded-xl bg-surface0 border border-surface1 p-4 shadow-sm">
          <p className="text-xs text-subtext0 uppercase font-medium">Total Goals</p>
          <p className="text-2xl font-bold text-peach mt-1">{totalGoals}</p>
        </Card>
        <Card className="rounded-xl bg-surface0 border border-surface1 p-4 shadow-sm">
          <p className="text-xs text-subtext0 uppercase font-medium">Goals / Match</p>
          <p className="text-2xl font-bold text-green mt-1">{avgGoals}</p>
        </Card>
      </div>

      {/* Standings Table */}
      {rankings.length === 0 ? (
        <EmptyState icon="📋" message="No standings found for this competition and season." />
      ) : (
        <div className="rounded-xl border border-surface1 bg-surface0 overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="border-b border-surface1 bg-mantle text-xs uppercase text-subtext0">
                <tr>
                  <th className="py-3 px-3 w-12 text-center">Pos</th>
                  <th className="py-3 px-4">Club</th>
                  <th className="py-3 px-3 text-center">P</th>
                  <th className="py-3 px-3 text-center">W</th>
                  <th className="py-3 px-3 text-center">D</th>
                  <th className="py-3 px-3 text-center">L</th>
                  <th className="py-3 px-3 text-center">GF</th>
                  <th className="py-3 px-3 text-center">GA</th>
                  <th className="py-3 px-3 text-center">GD</th>
                  <th className="py-3 px-3 text-center font-bold text-text">Pts</th>
                  <th className="py-3 px-3 text-right">PPG</th>
                  <th className="py-3 px-4 text-center">Form</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-surface1">
                {paginatedRankings.map((r) => {
                  const pos = r.rank;
                  const isUcl = pos <= 4;
                  const isUel = pos === 5 || pos === 6;
                  const isRelegation = pos >= rankings.length - 2;

                  return (
                    <tr key={r.team.team_id} className="hover:bg-surface1/40 transition-colors">
                      <td className="py-3 px-3 text-center font-mono text-xs font-semibold">
                        <span
                          className={`inline-flex items-center justify-center h-6 w-6 rounded-full text-xs ${
                            isUcl
                              ? 'bg-blue/20 text-blue font-bold'
                              : isUel
                              ? 'bg-teal/20 text-teal font-bold'
                              : isRelegation
                              ? 'bg-red/20 text-red font-bold'
                              : 'text-subtext0'
                          }`}
                        >
                          {pos}
                        </span>
                      </td>
                      <td className="py-3 px-4 font-semibold text-text flex items-center gap-2.5">
                        <FootballBadge url={r.team.badge_url} name={r.team.name} size={22} />
                        <span>{r.team.name}</span>
                      </td>
                      <td className="py-3 px-3 text-center text-subtext1">{r.played}</td>
                      <td className="py-3 px-3 text-center text-green font-medium">{r.wins}</td>
                      <td className="py-3 px-3 text-center text-yellow font-medium">{r.draws}</td>
                      <td className="py-3 px-3 text-center text-red font-medium">{r.losses}</td>
                      <td className="py-3 px-3 text-center text-subtext1">{r.goals_for}</td>
                      <td className="py-3 px-3 text-center text-subtext1">{r.goals_against}</td>
                      <td className={`py-3 px-3 text-center font-mono text-xs font-semibold ${
                        r.goal_difference > 0 ? 'text-green' : r.goal_difference < 0 ? 'text-red' : 'text-subtext0'
                      }`}>
                        {r.goal_difference > 0 ? `+${r.goal_difference}` : r.goal_difference}
                      </td>
                      <td className="py-3 px-3 text-center font-bold text-blue text-base">{r.points}</td>
                      <td className="py-3 px-3 text-right font-mono text-xs text-subtext0">{r.points_per_game.toFixed(2)}</td>
                      <td className="py-3 px-4 text-center">
                        <div className="flex items-center justify-center gap-1">
                          {(r.form || '').split(' ').map((char, ci) => {
                            const bg = char === 'W' ? 'bg-green/20 text-green' : char === 'D' ? 'bg-yellow/20 text-yellow' : 'bg-red/20 text-red';
                            return (
                              <span key={ci} className={`h-5 w-5 rounded text-[10px] font-bold flex items-center justify-center ${bg}`}>
                                {char}
                              </span>
                            );
                          })}
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>

          <div className="px-4 bg-mantle border-t border-surface1">
            <TablePagination />
          </div>

          {/* Table Legend */}
          <div className="flex flex-wrap items-center gap-6 p-4 border-t border-surface1 bg-mantle text-xs text-subtext0">
            <div className="flex items-center gap-2">
              <span className="h-3 w-3 rounded-full bg-blue" />
              <span>Champions League spot (1-4)</span>
            </div>
            <div className="flex items-center gap-2">
              <span className="h-3 w-3 rounded-full bg-teal" />
              <span>Europa League spot (5-6)</span>
            </div>
            <div className="flex items-center gap-2">
              <span className="h-3 w-3 rounded-full bg-red" />
              <span>Relegation zone (bottom 3)</span>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default function TablesPage() {
  return (
    <div className="space-y-6">
      <PageHeader icon={TableIcon} eyebrow="Standings" title="League Tables" description="Reconstruct domestic standings with venue splits, goal difference and recent form in one responsive table." />

      <Suspense fallback={<LoadingSkeleton lines={10} />}>
        <LeagueTablesContent />
      </Suspense>
    </div>
  );
}
