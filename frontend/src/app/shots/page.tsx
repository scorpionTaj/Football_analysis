'use client';

import { Suspense, useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Crosshair } from 'lucide-react';
import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Scatter,
  ScatterChart,
  Tooltip,
  XAxis,
  YAxis,
  ZAxis,
} from 'recharts';
import { api } from '@/lib/api/client';
import { queryKeys } from '@/lib/api/query-keys';
import { useFilterParams } from '@/lib/hooks/use-filter-params';
import { FilterBar } from '@/components/filters';
import { FootballBadge } from '@/lib/media-utils';
import { ErrorMessage, EmptyState, LoadingSkeleton } from '@/components/ui/loading';
import { PageHeader } from '@/components/ui/page-header';
import { SourceBadge } from '@/components/ui/source-badge';
import { usePagination } from '@/components/ui/pagination';
import { axisProps, gridProps, SERIES, tooltipProps } from '@/lib/chart-theme';
import { Panel } from '@/components/ui/panel';
import { Stat, StatGrid } from '@/components/ui/stat';
import { Chip } from '@/components/ui/chip';
import { DataTable, TBody, THead, Td, Th } from '@/components/ui/data-table';

function ShotIntelligenceContent() {
  const filters = useFilterParams();
  const request = useMemo(() => ({
    competition: filters.competition || undefined,
    season: filters.season || undefined,
    team: filters.team || undefined,
  }), [filters.competition, filters.season, filters.team]);
  const { data, isLoading, error, refetch } = useQuery({
    queryKey: queryKeys.shots(request),
    queryFn: () => api.shots(request),
  });

  const teams = useMemo(() => data?.teams ?? [], [data?.teams]);
  const coverage = data?.coverage ?? [];
  const averages = useMemo(() => {
    if (!teams.length) return { coverage: 0, shots: 0, accuracy: 0 };
    return {
      coverage: teams.reduce((sum, row) => sum + row.coverage_pct, 0) / teams.length,
      shots: teams.reduce((sum, row) => sum + (row.shots_per_match ?? 0), 0) / teams.length,
      accuracy: teams.reduce((sum, row) => sum + (row.shot_accuracy_pct ?? 0), 0) / teams.length,
    };
  }, [teams]);
  const volume = useMemo(() => [...teams].sort((a, b) => (b.shots_per_match ?? 0) - (a.shots_per_match ?? 0)).slice(0, 12), [teams]);
  const scatterTeams = useMemo(() => teams.slice(0, 160), [teams]);
  const { paginatedItems, paginationControls } = usePagination(teams, 10);

  const formatPercent = (value: number | null) => value === null ? '—' : `${value.toFixed(1)}%`;

  if (isLoading) return <LoadingSkeleton lines={10} />;
  if (error) return <ErrorMessage title="Shot intelligence could not load" detail={error.message} retry={() => refetch()} />;

  return (
    <div className="space-y-4">
      <Panel bodyClassName="flex flex-col justify-between gap-3 xl:flex-row xl:items-end">
        <FilterBar showVenue={false} />
        <div className="flex items-center gap-2">
          <Chip tone="positive">95% coverage gate</Chip>
          {data?.source ? <SourceBadge meta={data.source} /> : null}
        </div>
      </Panel>

      <StatGrid>
        <Stat label="Eligible club-seasons" value={teams.length.toLocaleString()} />
        <Stat label="Average coverage" value={`${averages.coverage.toFixed(1)}%`} />
        <Stat label="Shots per match" value={averages.shots.toFixed(1)} />
        <Stat label="On-target rate" value={`${averages.accuracy.toFixed(1)}%`} />
      </StatGrid>

      {!teams.length ? (
        <Panel><EmptyState icon={Crosshair} message="No club-season passes the shot coverage gate" suggestion="Choose another competition or season. Missing shot values are never treated as zero." /></Panel>
      ) : (
        <div className="grid gap-4 xl:grid-cols-2">
          <Panel title="Accuracy vs finishing efficiency" description="Bubble size is shot volume; up to 160 qualified rows.">
            <div className="h-80 w-full">
              <ResponsiveContainer width="100%" height="100%">
                <ScatterChart margin={{ top: 8, right: 12, bottom: 4, left: -12 }}>
                  <CartesianGrid {...gridProps} vertical />
                  <XAxis type="number" dataKey="shot_accuracy_pct" name="On target" unit="%" {...axisProps} />
                  <YAxis type="number" dataKey="goals_per_shot_pct" name="Goals per shot" unit="%" {...axisProps} />
                  <ZAxis type="number" dataKey="shots_per_match" range={[40, 320]} />
                  <Tooltip {...tooltipProps} cursor={{ strokeDasharray: '3 3' }} />
                  <Scatter data={scatterTeams} name="Club-seasons" fill={SERIES[0]} fillOpacity={0.55} stroke={SERIES[0]} />
                </ScatterChart>
              </ResponsiveContainer>
            </div>
          </Panel>
          <Panel title="Highest shot volume" description="Top eligible teams in the selected slice">
            <div className="h-80 w-full">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={volume} layout="vertical" margin={{ top: 0, right: 12, bottom: 0, left: 8 }}>
                  <CartesianGrid {...gridProps} vertical horizontal={false} />
                  <XAxis type="number" {...axisProps} />
                  <YAxis type="category" dataKey="team.name" width={110} {...axisProps} />
                  <Tooltip {...tooltipProps} />
                  <Bar dataKey="shots_per_match" name="Shots / match" fill={SERIES[0]} radius={[0, 3, 3, 0]} maxBarSize={18} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </Panel>
        </div>
      )}

      <Panel
        title="Qualified club-seasons"
        description="Conversion and accuracy stay empty when the source cannot support them."
        actions={<span className="text-xs tabular-nums text-subtext0">{coverage.length} coverage partitions</span>}
        bodyClassName="p-0"
      >
        <DataTable minWidth={720} caption="Qualified club-seasons">
          <THead>
            <tr><Th>Club</Th><Th>Season</Th><Th align="right">Coverage</Th><Th align="right">Shots / match</Th><Th align="right">On target</Th><Th align="right">Goals / shot</Th></tr>
          </THead>
          <TBody>
            {paginatedItems.map((row) => (
              <tr key={`${row.competition}-${row.season}-${row.team.team_id}`}>
                <Td><span className="flex items-center gap-2 font-medium"><FootballBadge name={row.team.name} url={row.team.badge_url} size={20} />{row.team.name}</span></Td>
                <Td className="text-subtext1">{row.season}/{String(row.season + 1).slice(-2)}</Td>
                <Td align="right" className="text-subtext1">{row.coverage_pct.toFixed(1)}%</Td>
                <Td align="right">{row.shots_per_match?.toFixed(1) ?? '—'}</Td>
                <Td align="right">{formatPercent(row.shot_accuracy_pct)}</Td>
                <Td align="right">{formatPercent(row.goals_per_shot_pct)}</Td>
              </tr>
            ))}
          </TBody>
        </DataTable>
        <div className="px-4 pb-3">{paginationControls}</div>
      </Panel>
    </div>
  );
}

export default function ShotsPage() {
  return (
    <div className="space-y-5">
      <PageHeader icon={Crosshair} eyebrow="Chance creation and finishing" title="Shot Intelligence" description="Compare volume, accuracy and finishing only where the source clears the 95% completeness rule." />
      <Suspense fallback={<LoadingSkeleton lines={10} />}>
        <ShotIntelligenceContent />
      </Suspense>
    </div>
  );
}
