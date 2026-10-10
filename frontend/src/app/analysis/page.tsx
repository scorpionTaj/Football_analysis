'use client';

import { Suspense, useMemo, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { api } from '@/lib/api/client';
import { toCsv } from '@/lib/csv';
import { queryKeys } from '@/lib/api/query-keys';
import { useFilterParams } from '@/lib/hooks/use-filter-params';
import { SourceBadge } from '@/components/ui/source-badge';
import { LoadingSkeleton, ErrorMessage, EmptyState } from '@/components/ui/loading';
import { PageHeader } from '@/components/ui/page-header';
import { usePagination } from '@/components/ui/pagination';
import { BarChart3, Download } from 'lucide-react';
import { Button } from '@heroui/react';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  CartesianGrid,
} from 'recharts';
import { axisProps, gridProps, tooltipProps } from '@/lib/chart-theme';
import { Panel } from '@/components/ui/panel';
import { Select } from '@/components/ui/select';
import { Stat, StatGrid } from '@/components/ui/stat';
import { FormChip } from '@/components/ui/chip';
import { DataTable, SortTh, TableFilter, TBody, THead, Td, Th } from '@/components/ui/data-table';
import { useTableView } from '@/lib/hooks/use-table-view';
import { RANKING_COLUMNS, rankingSearch } from '@/lib/table-columns';
import { FootballBadge } from '@/lib/media-utils';

interface MetricConfig {
  key: 'points_per_game' | 'goals_per_game' | 'conceded_per_game' | 'win_rate' | 'clean_sheet_rate' | 'form_ppg';
  label: string;
  color: string;
  reverse?: boolean;
}

const METRIC_CONFIGS: MetricConfig[] = [
  { key: 'points_per_game', label: 'Points per game (PPG)', color: 'var(--series-1)' },
  { key: 'goals_per_game', label: 'Goals scored / match', color: 'var(--series-1)' },
  { key: 'conceded_per_game', label: 'Goals conceded / match', color: 'var(--series-2)', reverse: true },
  { key: 'win_rate', label: 'Win rate (%)', color: 'var(--series-1)' },
  { key: 'clean_sheet_rate', label: 'Clean sheet rate (%)', color: 'var(--series-1)' },
  { key: 'form_ppg', label: 'Recent form PPG', color: 'var(--series-1)' },
];

type MetricKey = MetricConfig['key'];

function AnalysisContent() {
  const filters = useFilterParams();
  const [selectedMetric, setSelectedMetric] = useState<MetricKey>('points_per_game');
  const [teamLimit, setTeamLimit] = useState<number>(15);
  const [formWindow, setFormWindow] = useState<number>(5);

  const { data: catalog } = useQuery({
    queryKey: queryKeys.catalog,
    queryFn: () => api.catalog(),
  });

  const selectedCompetitions = useMemo(() => {
    return filters.competition ? [filters.competition] : ['E0'];
  }, [filters.competition]);

  // The selected competition's latest season (not the latest across every competition).
  const defaultSeason = useMemo(() => {
    const seasons = catalog?.competitions.find((c) => c.code === selectedCompetitions[0])?.seasons || [];
    return seasons.length ? Math.max(...seasons.map((s) => s.season)) : catalog?.current_season;
  }, [catalog, selectedCompetitions]);

  const selectedSeasons = useMemo(() => {
    const season = filters.season || defaultSeason;
    return season ? [season] : [];
  }, [filters.season, defaultSeason]);

  const requestBody = useMemo(() => ({
    competitions: selectedCompetitions,
    seasons: selectedSeasons,
    teams: filters.team ? [filters.team] : [],
    venue: filters.venue || null,
    form_window: formWindow,
  }), [selectedCompetitions, selectedSeasons, filters.team, filters.venue, formWindow]);

  const { data, isLoading, error, refetch } = useQuery({
    queryKey: queryKeys.analysis(requestBody),
    queryFn: () => api.analysis(requestBody),
    enabled: selectedSeasons.length > 0,
  });

  const rankings = useMemo(() => data?.rankings || [], [data?.rankings]);
  const table = useTableView(rankings, { columns: RANKING_COLUMNS, initial: { key: 'rank', dir: 'asc' }, search: rankingSearch });
  const { paginatedItems: paginatedRankings, paginationControls: AnalysisPagination } = usePagination(table.rows, 10);
  const matchFactors = data?.match_factors;
  const correlationMetrics = useMemo(() => {
    const first = data?.correlations?.[0];
    return first ? Object.keys(first).filter((key) => key !== 'metric') : [];
  }, [data?.correlations]);

  // Active metric config
  const metricInfo = METRIC_CONFIGS.find((m) => m.key === selectedMetric) || METRIC_CONFIGS[0];

  // Chart data sorted by active metric
  const chartData = useMemo(() => {
    const sorted = [...rankings].sort((a, b) => {
      const valA = (a[selectedMetric] as number) ?? 0;
      const valB = (b[selectedMetric] as number) ?? 0;
      return metricInfo.reverse ? valA - valB : valB - valA;
    });
    return sorted.slice(0, teamLimit).map((r) => ({
      name: r.team.name,
      value: Number(((r[selectedMetric] as number) ?? 0).toFixed(2)),
      rank: r.rank,
    }));
  }, [rankings, selectedMetric, teamLimit, metricInfo.reverse]);

  // CSV export handler
  const exportCsv = () => {
    const headers = [
      'Rank', 'Team', 'Competition', 'Played', 'W', 'D', 'L', 'Points',
      'PPG', 'GF', 'GA', 'GD', 'Win Rate %', 'Clean Sheet %', 'Form', 'Form PPG',
    ];
    const rows = rankings.map((r) => [
      r.rank,
      r.team.name,
      r.competition,
      r.played,
      r.wins,
      r.draws,
      r.losses,
      r.points,
      r.points_per_game.toFixed(2),
      r.goals_for,
      r.goals_against,
      r.goal_difference,
      r.win_rate.toFixed(1),
      r.clean_sheet_rate.toFixed(1),
      r.form || '',
      r.form_ppg !== null ? r.form_ppg.toFixed(2) : '',
    ]);
    const csvContent = toCsv(headers, rows);
    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.setAttribute('href', url);
    link.setAttribute('download', `analysis_rankings_${selectedCompetitions.join('_')}.csv`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  if (isLoading) return <LoadingSkeleton lines={8} />;
  if (error) {
    return <ErrorMessage title="Analysis calculation failed" detail={error.message} retry={() => refetch()} />;
  }

  const compOptions = catalog?.competitions || [];

  const mean = (pick: (row: typeof rankings[number]) => number) =>
    rankings.length ? rankings.reduce((sum, row) => sum + pick(row), 0) / rankings.length : 0;
  const fixed = (value: number | null | undefined, digits = 2) => (value == null ? 'N/A' : value.toFixed(digits));

  return (
    <div className="space-y-4">
      <Panel title="Analysis scope" actions={data?.source && <SourceBadge meta={data.source} />}>
        <div className="grid grid-cols-2 gap-3 sm:flex sm:flex-wrap sm:items-end">
          <Select label="Competition" value={selectedCompetitions[0]} onChange={(value) => filters.set({ competition: value })}
            options={compOptions.map((c) => ({ value: c.code, label: c.name }))} className="sm:w-52" />
          <Select label="Season" value={String(selectedSeasons[0] ?? '')} onChange={(value) => filters.set({ season: Number(value) })}
            options={(compOptions.find((c) => c.code === selectedCompetitions[0])?.seasons || []).map((season) => ({ value: String(season.season), label: season.label }))} className="sm:w-32" />
          <Select label="Venue" value={filters.venue || ''} onChange={(value) => filters.set({ venue: value || null })} placeholder="All venues"
            options={[{ value: 'Home', label: 'Home' }, { value: 'Away', label: 'Away' }]} className="sm:w-36" />
          <Select label="Form window" value={String(formWindow)} onChange={(value) => setFormWindow(Number(value))}
            options={[3, 5, 8, 10].map((n) => ({ value: String(n), label: `Last ${n} matches` }))} className="sm:w-40" />
        </div>
      </Panel>

      <StatGrid>
        <Stat label="Matches analysed" value={data?.match_count.toLocaleString() ?? '0'} />
        <Stat label="Teams ranked" value={rankings.length} />
        <Stat label="Avg goals / match" value={mean((row) => row.goals_per_game).toFixed(2)} />
        <Stat label="Avg clean-sheet rate" value={`${mean((row) => row.clean_sheet_rate).toFixed(1)}%`} />
      </StatGrid>

      <Panel
        title="Team performance ranking"
        actions={<>
          <Select hideLabel label="Ranking metric" value={selectedMetric} onChange={(value) => setSelectedMetric(value as MetricKey)}
            options={METRIC_CONFIGS.map((m) => ({ value: m.key, label: m.label }))} className="w-52" />
          <Select hideLabel label="Teams shown" value={String(teamLimit)} onChange={(value) => setTeamLimit(Number(value))}
            options={[['10', 'Top 10'], ['15', 'Top 15'], ['20', 'Top 20'], ['30', 'All']].map(([value, label]) => ({ value, label }))} className="w-28" />
        </>}
      >
        <div className="w-full" style={{ height: Math.max(240, chartData.length * 24 + 40) }}>
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={chartData} layout="vertical" margin={{ top: 0, right: 16, left: 8, bottom: 0 }}>
              <CartesianGrid {...gridProps} vertical horizontal={false} />
              <XAxis type="number" {...axisProps} />
              <YAxis type="category" dataKey="name" {...axisProps} width={120} />
              <Tooltip {...tooltipProps} formatter={(val) => [`${val}`, metricInfo.label]} />
              <Bar dataKey="value" fill={metricInfo.color} radius={[0, 3, 3, 0]} maxBarSize={18} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </Panel>

      <Panel
        title="Standings and performance breakdown"
        actions={<>
          <TableFilter label="Filter teams" placeholder="Filter teams…" value={table.query} onChange={table.setQuery} shown={table.rows.length} total={table.total} />
          <Button size="sm" variant="outline" onPress={exportCsv}><Download className="size-3.5" aria-hidden="true" /> Export CSV</Button>
        </>}
        bodyClassName="p-0"
      >
        {rankings.length === 0 ? (
          <EmptyState icon={BarChart3} message="No matches in this slice." suggestion="Widen the competition, season, team or venue filters." />
        ) : (
          <>
            <DataTable minWidth={900} caption="Analysis rankings">
              <THead>
                <tr>
                  <SortTh {...table.sortProps('rank')}>#</SortTh><SortTh {...table.sortProps('team')}>Team</SortTh>
                  <SortTh align="right" {...table.sortProps('played')}>P</SortTh><SortTh align="right" {...table.sortProps('wins')}>W</SortTh>
                  <SortTh align="right" {...table.sortProps('draws')}>D</SortTh><SortTh align="right" {...table.sortProps('losses')}>L</SortTh>
                  <SortTh align="right" {...table.sortProps('points')}>Pts</SortTh><SortTh align="right" {...table.sortProps('ppg')}>PPG</SortTh>
                  <SortTh align="right" {...table.sortProps('gfPerGame')}>GF/m</SortTh><SortTh align="right" {...table.sortProps('gaPerGame')}>GA/m</SortTh>
                  <SortTh align="right" {...table.sortProps('winRate')}>Win %</SortTh><SortTh align="right" {...table.sortProps('cleanSheets')}>Clean %</SortTh>
                  <SortTh align="center" {...table.sortProps('formPpg')}>Form (last {formWindow})</SortTh>
                </tr>
              </THead>
              <TBody>
                {paginatedRankings.map((r) => (
                  <tr key={r.team.team_id}>
                    <Td className="text-subtext0">{r.rank}</Td>
                    <Td><span className="flex items-center gap-2 font-medium"><FootballBadge url={r.team.badge_url} name={r.team.name} size={18} />{r.team.name}</span></Td>
                    <Td align="right" className="text-subtext1">{r.played}</Td>
                    <Td align="right" className="text-subtext1">{r.wins}</Td>
                    <Td align="right" className="text-subtext1">{r.draws}</Td>
                    <Td align="right" className="text-subtext1">{r.losses}</Td>
                    <Td align="right" className="font-semibold">{r.points}</Td>
                    <Td align="right">{r.points_per_game.toFixed(2)}</Td>
                    <Td align="right" className="text-subtext1">{r.goals_per_game.toFixed(2)}</Td>
                    <Td align="right" className="text-subtext1">{r.conceded_per_game.toFixed(2)}</Td>
                    <Td align="right" className="text-subtext1">{r.win_rate.toFixed(1)}%</Td>
                    <Td align="right" className="text-subtext1">{r.clean_sheet_rate.toFixed(1)}%</Td>
                    <Td align="center">
                      <span className="inline-flex gap-1">{(r.form || '').split(' ').filter(Boolean).map((result, i) => <FormChip key={i} result={result} />)}</span>
                    </Td>
                  </tr>
                ))}
              </TBody>
            </DataTable>
            <div className="px-4 pb-3">{AnalysisPagination}</div>
          </>
        )}
      </Panel>

      {data?.correlations?.length && correlationMetrics.length ? (
        <Panel title="Metric correlation matrix" description="Values near +1 move together; values near −1 move in opposite directions." bodyClassName="p-0">
          <DataTable minWidth={640} caption="Metric correlation matrix">
            <THead>
              <tr><Th>Metric</Th>{correlationMetrics.map((metric) => <Th key={metric} align="center" className="capitalize">{metric.replaceAll('_', ' ')}</Th>)}</tr>
            </THead>
            <TBody>
              {data.correlations.map((row) => (
                <tr key={String(row.metric)}>
                  <th scope="row" className="h-9 px-3 text-left font-medium capitalize text-text">{String(row.metric).replaceAll('_', ' ')}</th>
                  {correlationMetrics.map((metric) => {
                    const value = typeof row[metric] === 'number' ? row[metric] as number : null;
                    const tint = value == null ? null : `color-mix(in srgb, var(${value >= 0 ? '--blue' : '--red'}) ${Math.round(Math.min(1, Math.abs(value)) * 30)}%, transparent)`;
                    return <Td key={metric} align="center" style={{ background: tint ?? undefined }}>{value == null ? '—' : value.toFixed(2)}</Td>;
                  })}
                </tr>
              ))}
            </TBody>
          </DataTable>
        </Panel>
      ) : null}

      {matchFactors && (
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
          <Panel title="In-match factors" description="Means per match in this slice">
            <div className="grid grid-cols-2 gap-2">
              <Stat inset label="1st-half goals" value={fixed(matchFactors.first_half_goals_mean)} />
              <Stat inset label="2nd-half goals" value={fixed(matchFactors.second_half_goals_mean)} />
              <Stat inset label="Corners" value={fixed(matchFactors.corners_mean)} />
              <Stat inset label="Fouls" value={fixed(matchFactors.fouls_mean)} />
            </div>
          </Panel>
          <Panel title="Referee discipline" description="Most active referees in this slice" bodyClassName="p-0">
            <DataTable minWidth={360} caption="Referee discipline">
              <THead><tr><Th>Referee</Th><Th align="right">Matches</Th><Th align="right">Yellows / m</Th><Th align="right">Reds / m</Th></tr></THead>
              <TBody>
                {(matchFactors.referees || []).slice(0, 5).map((ref) => (
                  <tr key={ref.referee}>
                    <Td className="font-medium">{ref.referee}</Td>
                    <Td align="right" className="text-subtext1">{ref.matches}</Td>
                    <Td align="right">{ref.yellow_cards_mean?.toFixed(2) ?? '–'}</Td>
                    <Td align="right">{ref.red_cards_mean?.toFixed(2) ?? '–'}</Td>
                  </tr>
                ))}
              </TBody>
            </DataTable>
          </Panel>
        </div>
      )}
    </div>
  );
}

export default function AnalysisPage() {
  return (
    <div className="space-y-5">
      <PageHeader icon={BarChart3} eyebrow="Compare and explain" title="Analysis Lab" description="Compare competitions, form, match factors and disciplinary patterns from one filterable workspace." />

      <Suspense fallback={<LoadingSkeleton lines={8} />}>
        <AnalysisContent />
      </Suspense>
    </div>
  );
}
