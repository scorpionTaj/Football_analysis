'use client';

import { Suspense, useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Card, Chip } from '@heroui/react';
import { Crosshair, Gauge, ShieldCheck, Target, Zap } from 'lucide-react';
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
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
import { tooltipProps } from '@/lib/chart-theme';

const COLORS = ['var(--series-1)', 'var(--teal)', 'var(--green)', 'var(--yellow)', 'var(--series-2)', 'var(--series-3)'];

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
    <div className="space-y-6">
      <Card className="rounded-2xl border border-surface1 bg-surface0/80 p-4 shadow-sm">
        <div className="flex flex-col justify-between gap-4 xl:flex-row xl:items-end">
          <FilterBar showVenue={false} />
          <div className="flex items-center gap-2">
            <Chip color="success" variant="soft">95% coverage gate</Chip>
            {data?.source ? <SourceBadge meta={data.source} /> : null}
          </div>
        </div>
      </Card>

      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        {[
          { label: 'Eligible club-seasons', value: teams.length.toLocaleString(), icon: ShieldCheck, color: 'text-green' },
          { label: 'Average coverage', value: `${averages.coverage.toFixed(1)}%`, icon: Gauge, color: 'text-blue' },
          { label: 'Shots per match', value: averages.shots.toFixed(1), icon: Zap, color: 'text-peach' },
          { label: 'On-target rate', value: `${averages.accuracy.toFixed(1)}%`, icon: Target, color: 'text-mauve' },
        ].map((metric) => (
          <Card key={metric.label} className="rounded-2xl border border-surface1 bg-surface0/80 p-4 shadow-sm sm:p-5">
            <div className="flex items-start justify-between gap-3">
              <div>
                <p className="text-xs font-semibold text-subtext0">{metric.label}</p>
                <p className={`mt-2 text-2xl font-black tracking-tight sm:text-3xl ${metric.color}`}>{metric.value}</p>
              </div>
              <metric.icon className={`size-5 ${metric.color}`} aria-hidden="true" />
            </div>
          </Card>
        ))}
      </div>

      {!teams.length ? (
        <EmptyState icon="🎯" message="No club-season passes the shot coverage gate" suggestion="Choose another competition or season. Missing shot values are never treated as zero." />
      ) : (
        <div className="grid gap-6 xl:grid-cols-2">
          <Card className="rounded-2xl border border-surface1 bg-surface0/80 p-4 shadow-sm sm:p-5">
            <div className="mb-5">
              <h2 className="font-bold text-text">Accuracy vs finishing efficiency</h2>
              <p className="mt-1 text-sm text-subtext0">Bubble size represents shot volume. Showing up to 160 qualified rows for a responsive chart.</p>
            </div>
            <div className="h-80 w-full">
              <ResponsiveContainer width="100%" height="100%">
                <ScatterChart margin={{ top: 10, right: 12, bottom: 12, left: -12 }}>
                  <CartesianGrid stroke="var(--surface1)" strokeDasharray="3 3" />
                  <XAxis type="number" dataKey="shot_accuracy_pct" name="On target" unit="%" stroke="var(--overlay1)" fontSize={11} />
                  <YAxis type="number" dataKey="goals_per_shot_pct" name="Goals per shot" unit="%" stroke="var(--overlay1)" fontSize={11} />
                  <ZAxis type="number" dataKey="shots_per_match" range={[70, 420]} />
                  <Tooltip {...tooltipProps} cursor={{ strokeDasharray: '3 3' }} />
                  <Scatter data={scatterTeams} name="Club-seasons" fill="var(--series-1)">
                    {scatterTeams.map((row, index) => <Cell key={`${row.team.team_id}-${row.season}`} fill={COLORS[index % COLORS.length]} />)}
                  </Scatter>
                </ScatterChart>
              </ResponsiveContainer>
            </div>
          </Card>

          <Card className="rounded-2xl border border-surface1 bg-surface0/80 p-4 shadow-sm sm:p-5">
            <div className="mb-5">
              <h2 className="font-bold text-text">Highest shot volume</h2>
              <p className="mt-1 text-sm text-subtext0">Top eligible teams in the selected slice.</p>
            </div>
            <div className="h-80 w-full">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={volume} layout="vertical" margin={{ top: 0, right: 12, bottom: 0, left: 28 }}>
                  <CartesianGrid stroke="var(--surface1)" strokeDasharray="3 3" horizontal={false} />
                  <XAxis type="number" stroke="var(--overlay1)" fontSize={11} />
                  <YAxis type="category" dataKey="team.name" width={100} stroke="var(--overlay1)" fontSize={10} />
                  <Tooltip {...tooltipProps} />
                  <Bar dataKey="shots_per_match" name="Shots / match" fill="var(--teal)" radius={[0, 8, 8, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </Card>
        </div>
      )}

      <Card className="overflow-hidden rounded-2xl border border-surface1 bg-surface0/80 shadow-sm">
        <div className="flex flex-col gap-2 border-b border-surface1 px-4 py-4 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <h2 className="font-bold text-text">Qualified club-seasons</h2>
            <p className="text-sm text-subtext0">Conversion and accuracy stay nullable when the source cannot support them.</p>
          </div>
          <span className="text-xs font-semibold text-subtext0">{coverage.length} coverage partitions</span>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full min-w-[760px] text-left text-sm">
            <thead className="bg-mantle text-xs uppercase tracking-wide text-subtext0">
              <tr>
                <th className="px-4 py-3">Club</th><th className="px-3 py-3">Season</th><th className="px-3 py-3 text-right">Coverage</th><th className="px-3 py-3 text-right">Shots / match</th><th className="px-3 py-3 text-right">On target</th><th className="px-4 py-3 text-right">Goals / shot</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-surface1/70">
              {paginatedItems.map((row) => (
                <tr key={`${row.competition}-${row.season}-${row.team.team_id}`} className="hover:bg-surface1/30">
                  <td className="px-4 py-3"><span className="flex items-center gap-2 font-semibold text-text"><FootballBadge name={row.team.name} url={row.team.badge_url} size={26} />{row.team.name}</span></td>
                  <td className="px-3 py-3 text-subtext1">{row.season}/{String(row.season + 1).slice(-2)}</td>
                  <td className="px-3 py-3 text-right font-mono text-green">{row.coverage_pct.toFixed(1)}%</td>
                  <td className="px-3 py-3 text-right font-mono">{row.shots_per_match?.toFixed(1) ?? '—'}</td>
                  <td className="px-3 py-3 text-right font-mono">{formatPercent(row.shot_accuracy_pct)}</td>
                  <td className="px-4 py-3 text-right font-mono">{formatPercent(row.goals_per_shot_pct)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div className="px-4">
          {paginationControls}
        </div>
      </Card>
    </div>
  );
}

export default function ShotsPage() {
  return (
    <div className="space-y-6">
      <PageHeader icon={Crosshair} eyebrow="Chance creation and finishing" title="Shot Intelligence" description="Compare volume, accuracy and finishing only where the source clears the 95% completeness rule." />
      <Suspense fallback={<LoadingSkeleton lines={10} />}>
        <ShotIntelligenceContent />
      </Suspense>
    </div>
  );
}
