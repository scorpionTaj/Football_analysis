'use client';

import { Button } from '@heroui/react';
import { Suspense, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { api } from '@/lib/api/client';
import { toCsv } from '@/lib/csv';
import { queryKeys } from '@/lib/api/query-keys';
import { useFilterParams } from '@/lib/hooks/use-filter-params';
import { SourceBadge } from '@/components/ui/source-badge';
import { LoadingSkeleton, ErrorMessage, EmptyState } from '@/components/ui/loading';
import { PageHeader } from '@/components/ui/page-header';
import { Panel } from '@/components/ui/panel';
import { Select } from '@/components/ui/select';
import { Segmented } from '@/components/ui/segmented';
import { Stat, StatGrid } from '@/components/ui/stat';
import { FormChip } from '@/components/ui/chip';
import { DataTable, SortTh, TableFilter, TBody, THead, Td, Th } from '@/components/ui/data-table';
import { useTableView } from '@/lib/hooks/use-table-view';
import { RANKING_COLUMNS, rankingSearch } from '@/lib/table-columns';
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
  const latestSeason = seasons.length > 0 ? Math.max(...seasons.map((s) => s.season)) : catalog?.current_season;
  const selectedSeason = filters.season || latestSeason || 0;

  const { data: standingData, isLoading, error, refetch } = useQuery({
    queryKey: queryKeys.standings(selectedCompetition, selectedSeason, 5, venueFilter === 'All' ? undefined : venueFilter),
    queryFn: () => api.standings(selectedCompetition, selectedSeason, 5, venueFilter === 'All' ? undefined : venueFilter),
    enabled: selectedSeason > 0,  // wait for the catalog instead of guessing a year
  });

  const rankings = standingData?.rankings || [];
  const table = useTableView(rankings, { columns: RANKING_COLUMNS, initial: { key: 'rank', dir: 'asc' }, search: rankingSearch });
  const { paginatedItems: paginatedRankings, paginationControls: TablePagination } = usePagination(table.rows, 10);

  // Export CSV
  const exportCsv = () => {
    const headers = ['Pos', 'Team', 'P', 'W', 'D', 'L', 'GF', 'GA', 'GD', 'Pts', 'PPG', 'Form'];
    const rows = rankings.map((r) => [
      r.rank,
      r.team.name,
      r.played,
      r.wins,
      r.draws,
      r.losses,
      r.goals_for,
      r.goals_against,
      r.goal_difference,
      r.points,
      r.points_per_game.toFixed(2),
      r.form || '',
    ]);
    const csv = toCsv(headers, rows);
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
  const totalMatches = rankings.reduce((acc, r) => acc + r.played, 0) / 2;
  const avgGoals = totalMatches > 0 ? (totalGoals / totalMatches).toFixed(2) : '0';

  const zone = (pos: number) => pos <= 4 ? 'bg-accent' : pos <= 6 ? 'bg-[var(--series-3)]' : pos >= rankings.length - 2 ? 'bg-negative' : 'bg-transparent';
  const signed = (value: number | null | undefined) => value == null ? '—' : `${value > 0 ? '+' : ''}${value}`;

  return (
    <div className="space-y-4">
      <Panel bodyClassName="flex flex-col justify-between gap-4 sm:flex-row sm:items-end">
        <div className="flex flex-wrap items-end gap-3">
          <CompetitionBadge code={selectedCompetition} name={currentComp?.name || selectedCompetition} badge_url={currentComp?.badge_url} size={36} />
          <Select label="League" value={selectedCompetition} onChange={(value) => filters.set({ competition: value })}
            options={compOptions.map((c) => ({ value: c.code, label: c.name }))} className="w-48" />
          <Select label="Season" value={String(selectedSeason)} onChange={(value) => filters.set({ season: Number(value) })}
            options={seasons.map((season) => ({ value: String(season.season), label: season.label }))} className="w-32" />
          <div className="flex flex-col gap-1">
            <span className="text-xs font-medium text-subtext0">Venue</span>
            <Segmented label="Venue" value={venueFilter} onChange={setVenueFilter}
              options={[{ value: 'All', label: 'All' }, { value: 'Home', label: 'Home' }, { value: 'Away', label: 'Away' }]} />
          </div>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {standingData?.source && <SourceBadge meta={standingData.source} />}
          <Button size="sm" variant="outline" onPress={exportCsv}>
            <Download className="size-3.5" aria-hidden="true" /> Export CSV
          </Button>
        </div>
      </Panel>

      <StatGrid>
        <Stat label="Clubs" value={rankings.length} />
        <Stat label="Matches played" value={totalMatches} />
        <Stat label="Total goals" value={totalGoals} />
        <Stat label="Goals / match" value={avgGoals} />
      </StatGrid>

      {rankings.length === 0 ? (
        <Panel><EmptyState icon={TableIcon} message="No standings found for this competition and season." /></Panel>
      ) : (
        <Panel title="Standings" actions={<TableFilter label="Filter clubs" placeholder="Filter clubs…" value={table.query} onChange={table.setQuery} shown={table.rows.length} total={table.total} />} bodyClassName="p-0">
          <DataTable minWidth={720} caption="League standings">
            <THead>
              <tr>
                <SortTh align="center" className="w-12" {...table.sortProps('rank')}>Pos</SortTh>
                <SortTh {...table.sortProps('team')}>Club</SortTh>
                <SortTh align="right" {...table.sortProps('played')}>P</SortTh>
                <SortTh align="right" {...table.sortProps('wins')}>W</SortTh>
                <SortTh align="right" {...table.sortProps('draws')}>D</SortTh>
                <SortTh align="right" {...table.sortProps('losses')}>L</SortTh>
                <SortTh align="right" {...table.sortProps('goalsFor')}>GF</SortTh>
                <SortTh align="right" {...table.sortProps('goalsAgainst')}>GA</SortTh>
                <SortTh align="right" {...table.sortProps('goalDifference')}>GD</SortTh>
                <SortTh align="right" {...table.sortProps('points')}>Pts</SortTh>
                <SortTh align="right" {...table.sortProps('ppg')}>PPG</SortTh>
                <Th align="center">Form</Th>
              </tr>
            </THead>
            <TBody>
              {paginatedRankings.map((r) => (
                <tr key={r.team.team_id}>
                  <Td align="center" className="relative text-subtext0">
                    <span className={`absolute inset-y-1.5 left-0 w-0.5 rounded-r ${zone(r.rank)}`} aria-hidden="true" />
                    {r.rank}
                  </Td>
                  <Td>
                    <span className="flex items-center gap-2 font-medium">
                      <FootballBadge url={r.team.badge_url} name={r.team.name} size={20} />
                      {r.team.name}
                    </span>
                  </Td>
                  <Td align="right" className="text-subtext1">{r.played}</Td>
                  <Td align="right" className="text-subtext1">{r.wins}</Td>
                  <Td align="right" className="text-subtext1">{r.draws}</Td>
                  <Td align="right" className="text-subtext1">{r.losses}</Td>
                  <Td align="right" className="text-subtext1">{r.goals_for}</Td>
                  <Td align="right" className="text-subtext1">{r.goals_against}</Td>
                  <Td align="right" className={r.goal_difference > 0 ? 'text-positive' : r.goal_difference < 0 ? 'text-negative' : 'text-subtext0'}>{signed(r.goal_difference)}</Td>
                  <Td align="right" className="font-semibold">{r.points}</Td>
                  <Td align="right" className="text-subtext0">{r.points_per_game.toFixed(2)}</Td>
                  <Td align="center">
                    <span className="inline-flex gap-1">
                      {(r.form || '').split(' ').filter(Boolean).map((result, index) => <FormChip key={index} result={result} />)}
                    </span>
                  </Td>
                </tr>
              ))}
            </TBody>
          </DataTable>
          <div className="px-4 pb-3">{TablePagination}</div>
          <div className="flex flex-wrap items-center gap-x-5 gap-y-2 border-t border-surface1 px-4 py-3 text-xs text-subtext0">
            <span className="inline-flex items-center gap-2"><span className="h-3 w-0.5 rounded bg-accent" aria-hidden="true" />Champions League (1–4)</span>
            <span className="inline-flex items-center gap-2"><span className="h-3 w-0.5 rounded bg-[var(--series-3)]" aria-hidden="true" />Europa League (5–6)</span>
            <span className="inline-flex items-center gap-2"><span className="h-3 w-0.5 rounded bg-negative" aria-hidden="true" />Relegation (bottom 3)</span>
          </div>
        </Panel>
      )}

      {venueFilter === 'All' ? (
        <Panel
          title="External reference validation"
          description="Reference minus results points exposes administrative adjustments; rank differences expose provider or tiebreak differences."
          bodyClassName="p-0"
        >
          {standingData?.reference.length ? (
            <DataTable minWidth={720} caption="External reference standings">
              <THead>
                <tr><Th>Ref</Th><Th>Club</Th><Th align="right">P</Th><Th align="right">Ref pts</Th><Th align="right">Results pts</Th><Th align="right">Adjustment</Th><Th align="right">Rank Δ</Th><Th>Qualification</Th></tr>
              </THead>
              <TBody>
                {standingData.reference.map((row) => (
                  <tr key={`${row.source_name}-${row.rank}-${row.team.team_id}`}>
                    <Td className="text-subtext0">{row.rank}</Td>
                    <Td><span className="flex items-center gap-2 font-medium"><FootballBadge url={row.team.badge_url} name={row.team.name} size={18} />{row.team.name}</span></Td>
                    <Td align="right">{row.played ?? '—'}</Td>
                    <Td align="right" className="font-semibold">{row.points ?? '—'}</Td>
                    <Td align="right">{row.results_points ?? '—'}</Td>
                    <Td align="right" className={(row.point_adjustment ?? 0) !== 0 ? 'text-warning' : 'text-subtext0'}>{signed(row.point_adjustment)}</Td>
                    <Td align="right" className="text-subtext0">{signed(row.rank_difference)}</Td>
                    <Td className="text-subtext0">{row.description || '—'}</Td>
                  </tr>
                ))}
              </TBody>
            </DataTable>
          ) : <p className="p-4 text-sm text-subtext0">No external reference table is cached for this competition and season.</p>}
        </Panel>
      ) : null}
    </div>
  );
}

export default function TablesPage() {
  return (
    <div className="space-y-5">
      <PageHeader icon={TableIcon} eyebrow="Standings" title="League Tables" description="Reconstruct domestic standings with venue splits, goal difference and recent form in one responsive table." />

      <Suspense fallback={<LoadingSkeleton lines={10} />}>
        <LeagueTablesContent />
      </Suspense>
    </div>
  );
}
