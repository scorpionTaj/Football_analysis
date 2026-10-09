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
import { BarChart3, TrendingUp, ShieldAlert, Award, Download, SlidersHorizontal } from 'lucide-react';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  CartesianGrid,
  Cell,
} from 'recharts';

interface MetricConfig {
  key: 'points_per_game' | 'goals_per_game' | 'conceded_per_game' | 'win_rate' | 'clean_sheet_rate' | 'form_ppg';
  label: string;
  color: string;
  reverse?: boolean;
}

const METRIC_CONFIGS: MetricConfig[] = [
  { key: 'points_per_game', label: 'Points per game (PPG)', color: '#89b4fa' },
  { key: 'goals_per_game', label: 'Goals scored / match', color: '#a6e3a1' },
  { key: 'conceded_per_game', label: 'Goals conceded / match', color: '#f38ba8', reverse: true },
  { key: 'win_rate', label: 'Win rate (%)', color: '#cba6f7' },
  { key: 'clean_sheet_rate', label: 'Clean sheet rate (%)', color: '#94e2d5' },
  { key: 'form_ppg', label: 'Recent Form PPG', color: '#fab387' },
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
  const { paginatedItems: paginatedRankings, paginationControls: AnalysisPagination } = usePagination(rankings, 10);
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

  return (
    <div className="space-y-6">
      {/* Filter Control Bar */}
      <div className="rounded-xl border border-surface1 bg-surface0 p-4 space-y-4">
        <div className="flex flex-wrap items-center justify-between gap-3 border-b border-surface1 pb-3">
          <div className="flex items-center gap-2">
            <SlidersHorizontal className="h-4 w-4 text-blue" />
            <span className="text-sm font-semibold text-text">Analysis Scope</span>
          </div>
          {data?.source && <SourceBadge meta={data.source} />}
        </div>

        <div className="flex flex-wrap items-center gap-4">
          {/* Competition */}
          <div className="flex flex-col gap-1">
            <label className="text-xs font-medium text-subtext0">Competition</label>
            <select
              value={selectedCompetitions[0]}
              onChange={(e) => filters.set({ competition: e.target.value })}
              className="rounded-lg border border-surface1 bg-mantle px-3 py-1.5 text-xs text-text outline-none hover:border-surface2 focus:border-blue cursor-pointer"
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
              value={selectedSeasons[0]}
              onChange={(e) => filters.set({ season: Number(e.target.value) })}
              className="rounded-lg border border-surface1 bg-mantle px-3 py-1.5 text-xs text-text outline-none hover:border-surface2 focus:border-blue cursor-pointer"
            >
              {(compOptions.find((c) => c.code === selectedCompetitions[0])?.seasons || []).map((s) => (
                <option key={s.season} value={s.season}>{s.label}</option>
              ))}
            </select>
          </div>

          {/* Venue */}
          <div className="flex flex-col gap-1">
            <label className="text-xs font-medium text-subtext0">Venue</label>
            <select
              value={filters.venue || ''}
              onChange={(e) => filters.set({ venue: e.target.value || null })}
              className="rounded-lg border border-surface1 bg-mantle px-3 py-1.5 text-xs text-text outline-none hover:border-surface2 focus:border-blue cursor-pointer"
            >
              <option value="">All Venues</option>
              <option value="Home">Home</option>
              <option value="Away">Away</option>
            </select>
          </div>

          {/* Form Window */}
          <div className="flex flex-col gap-1">
            <label className="text-xs font-medium text-subtext0">Form Window (Matches)</label>
            <select
              value={formWindow}
              onChange={(e) => setFormWindow(Number(e.target.value))}
              className="rounded-lg border border-surface1 bg-mantle px-3 py-1.5 text-xs text-text outline-none hover:border-surface2 focus:border-blue cursor-pointer"
            >
              <option value={3}>Last 3 matches</option>
              <option value={5}>Last 5 matches</option>
              <option value={8}>Last 8 matches</option>
              <option value={10}>Last 10 matches</option>
            </select>
          </div>
        </div>
      </div>

      {/* Summary KPI Cards */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
        <div className="rounded-xl bg-surface0 border border-surface1 p-4">
          <p className="text-xs font-medium text-subtext0 uppercase">Matches Analyzed</p>
          <p className="mt-1 text-2xl font-bold text-text">{data?.match_count.toLocaleString()}</p>
        </div>

        <div className="rounded-xl bg-surface0 border border-surface1 p-4">
          <p className="text-xs font-medium text-subtext0 uppercase">Teams Ranked</p>
          <p className="mt-1 text-2xl font-bold text-teal">{rankings.length}</p>
        </div>

        <div className="rounded-xl bg-surface0 border border-surface1 p-4">
          <p className="text-xs font-medium text-subtext0 uppercase">Avg Goals / Match</p>
          <p className="mt-1 text-2xl font-bold text-peach">
            {rankings.length > 0
              ? (rankings.reduce((s, r) => s + r.goals_per_game, 0) / rankings.length).toFixed(2)
              : '0'}
          </p>
        </div>

        <div className="rounded-xl bg-surface0 border border-surface1 p-4">
          <p className="text-xs font-medium text-subtext0 uppercase">Avg Clean Sheet Rate</p>
          <p className="mt-1 text-2xl font-bold text-mauve">
            {rankings.length > 0
              ? `${(rankings.reduce((s, r) => s + r.clean_sheet_rate, 0) / rankings.length).toFixed(1)}%`
              : '0%'}
          </p>
        </div>
      </div>

      {/* Interactive Ranking Chart Section */}
      <div className="rounded-xl border border-surface1 bg-surface0 p-5 space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div className="flex items-center gap-2">
            <BarChart3 className="h-4 w-4 text-blue" />
            <h2 className="text-base font-semibold text-text">Team Performance Ranking</h2>
          </div>

          <div className="flex items-center gap-3">
            {/* Metric selector */}
            <select
              value={selectedMetric}
              onChange={(e) => setSelectedMetric(e.target.value as MetricKey)}
              className="rounded-lg border border-surface1 bg-mantle px-3 py-1.5 text-xs font-medium text-text outline-none cursor-pointer"
            >
              {METRIC_CONFIGS.map((m) => (
                <option key={m.key} value={m.key}>{m.label}</option>
              ))}
            </select>

            {/* Teams shown slider/select */}
            <select
              value={teamLimit}
              onChange={(e) => setTeamLimit(Number(e.target.value))}
              className="rounded-lg border border-surface1 bg-mantle px-2.5 py-1.5 text-xs text-subtext0 outline-none cursor-pointer"
            >
              <option value={10}>Top 10</option>
              <option value={15}>Top 15</option>
              <option value={20}>Top 20</option>
              <option value={30}>All</option>
            </select>
          </div>
        </div>

        <div className="h-80 w-full">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={chartData} layout="vertical" margin={{ top: 10, right: 20, left: 40, bottom: 5 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#313244" horizontal={false} />
              <XAxis type="number" stroke="#7f849c" fontSize={11} />
              <YAxis type="category" dataKey="name" stroke="#7f849c" fontSize={11} width={110} />
              <Tooltip
                contentStyle={{ backgroundColor: '#181825', borderColor: '#45475a', borderRadius: '8px', color: '#cdd6f4' }}
                formatter={(val) => [`${val}`, metricInfo.label]}
              />
              <Bar dataKey="value" fill={metricInfo.color} radius={[0, 4, 4, 0]}>
                {chartData.map((_, index) => (
                  <Cell key={`cell-${index}`} fill={metricInfo.color} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Comprehensive Rankings Table */}
      <div className="rounded-xl border border-surface1 bg-surface0 overflow-hidden">
        <div className="flex items-center justify-between p-4 border-b border-surface1">
          <h2 className="text-base font-semibold text-text flex items-center gap-2">
            <Award className="h-4 w-4 text-yellow" /> Full Standings & Performance Breakdown
          </h2>
          <button
            onClick={exportCsv}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-mantle border border-surface1 hover:border-surface2 text-xs font-medium text-text transition-colors cursor-pointer"
          >
            <Download className="h-3.5 w-3.5 text-blue" />
            <span>Export CSV</span>
          </button>
        </div>

        {rankings.length === 0 ? (
          <EmptyState icon="📊" message="No matches in this slice." suggestion="Widen the competition, season, team or venue filters." />
        ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead className="border-b border-surface1 bg-mantle text-xs uppercase text-subtext0">
              <tr>
                <th className="py-3 px-4">#</th>
                <th className="py-3 px-4">Team</th>
                <th className="py-3 px-4 text-center">P</th>
                <th className="py-3 px-4 text-center">W</th>
                <th className="py-3 px-4 text-center">D</th>
                <th className="py-3 px-4 text-center">L</th>
                <th className="py-3 px-4 text-center">Pts</th>
                <th className="py-3 px-4 text-right">PPG</th>
                <th className="py-3 px-4 text-right">GF/m</th>
                <th className="py-3 px-4 text-right">GA/m</th>
                <th className="py-3 px-4 text-center">Win %</th>
                <th className="py-3 px-4 text-center">Clean %</th>
                <th className="py-3 px-4 text-center">Form (Last {formWindow})</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-surface1">
              {paginatedRankings.map((r) => (
                <tr key={r.team.team_id} className="hover:bg-surface1/40 transition-colors">
                  <td className="py-2.5 px-4 font-mono text-xs text-subtext0">{r.rank}</td>
                  <td className="py-2.5 px-4 font-semibold text-text">{r.team.name}</td>
                  <td className="py-2.5 px-4 text-center text-subtext1">{r.played}</td>
                  <td className="py-2.5 px-4 text-center text-green font-medium">{r.wins}</td>
                  <td className="py-2.5 px-4 text-center text-yellow font-medium">{r.draws}</td>
                  <td className="py-2.5 px-4 text-center text-red font-medium">{r.losses}</td>
                  <td className="py-2.5 px-4 text-center font-bold text-blue">{r.points}</td>
                  <td className="py-2.5 px-4 text-right font-mono text-xs">{r.points_per_game.toFixed(2)}</td>
                  <td className="py-2.5 px-4 text-right font-mono text-xs text-green">{r.goals_per_game.toFixed(2)}</td>
                  <td className="py-2.5 px-4 text-right font-mono text-xs text-red">{r.conceded_per_game.toFixed(2)}</td>
                  <td className="py-2.5 px-4 text-center text-xs">{r.win_rate.toFixed(1)}%</td>
                  <td className="py-2.5 px-4 text-center text-xs text-teal">{r.clean_sheet_rate.toFixed(1)}%</td>
                  <td className="py-2.5 px-4 text-center">
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
              ))}
            </tbody>
          </table>
        </div>
        )}
        <div className="px-4 py-3 bg-mantle border-t border-surface1">
          {AnalysisPagination}
        </div>
      </div>

      {data?.correlations?.length && correlationMetrics.length ? (
        <div className="overflow-hidden rounded-xl border border-surface1 bg-surface0">
          <div className="border-b border-surface1 p-4">
            <h2 className="font-semibold text-text">Metric correlation matrix</h2>
            <p className="mt-1 text-xs text-subtext0">Values near +1 move together; values near −1 move in opposite directions.</p>
          </div>
          <div className="overflow-x-auto p-4">
            <table className="w-full text-center text-xs">
              <thead><tr><th className="p-2 text-left text-subtext0">Metric</th>{correlationMetrics.map((metric) => <th key={metric} className="min-w-24 p-2 text-subtext0">{metric.replaceAll('_', ' ')}</th>)}</tr></thead>
              <tbody>
                {data.correlations.map((row) => <tr key={String(row.metric)}><th className="p-2 text-left font-semibold text-text">{String(row.metric).replaceAll('_', ' ')}</th>{correlationMetrics.map((metric) => {
                  const value = typeof row[metric] === 'number' ? row[metric] as number : null;
                  const intensity = value == null ? 0 : Math.min(0.32, Math.abs(value) * 0.32);
                  return <td key={metric} className="border border-surface1 p-2 font-mono text-text" style={{ backgroundColor: value == null ? undefined : value >= 0 ? `rgba(137,180,250,${intensity})` : `rgba(243,139,168,${intensity})` }}>{value == null ? '—' : value.toFixed(2)}</td>;
                })}</tr>)}
              </tbody>
            </table>
          </div>
        </div>
      ) : null}

      {/* Match Factors & Disciplinary Context */}
      {matchFactors && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div className="rounded-xl border border-surface1 bg-surface0 p-5 space-y-3">
            <h3 className="text-sm font-semibold text-text flex items-center gap-2">
              <TrendingUp className="h-4 w-4 text-teal" /> In-Match Scoring Distribution
            </h3>
            <div className="grid grid-cols-2 gap-3 pt-2">
              <div className="rounded-lg bg-mantle p-3 border border-surface1">
                <p className="text-xs text-subtext0">1st Half Goals (Mean)</p>
                <p className="text-lg font-bold text-text mt-1">{matchFactors.first_half_goals_mean?.toFixed(2) ?? 'N/A'}</p>
              </div>
              <div className="rounded-lg bg-mantle p-3 border border-surface1">
                <p className="text-xs text-subtext0">2nd Half Goals (Mean)</p>
                <p className="text-lg font-bold text-text mt-1">{matchFactors.second_half_goals_mean?.toFixed(2) ?? 'N/A'}</p>
              </div>
              <div className="rounded-lg bg-mantle p-3 border border-surface1">
                <p className="text-xs text-subtext0">Corners / Match (Mean)</p>
                <p className="text-lg font-bold text-text mt-1">{matchFactors.corners_mean?.toFixed(2) ?? 'N/A'}</p>
              </div>
              <div className="rounded-lg bg-mantle p-3 border border-surface1">
                <p className="text-xs text-subtext0">Fouls / Match (Mean)</p>
                <p className="text-lg font-bold text-text mt-1">{matchFactors.fouls_mean?.toFixed(2) ?? 'N/A'}</p>
              </div>
            </div>
          </div>

          {/* Referee Activity */}
          <div className="rounded-xl border border-surface1 bg-surface0 p-5 space-y-3">
            <h3 className="text-sm font-semibold text-text flex items-center gap-2">
              <ShieldAlert className="h-4 w-4 text-peach" /> Referee Disciplinary Impact
            </h3>
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead className="border-b border-surface1 text-subtext0 uppercase">
                  <tr>
                    <th className="py-2">Referee</th>
                    <th className="py-2 text-center">Matches</th>
                    <th className="py-2 text-right">Yellows / m</th>
                    <th className="py-2 text-right">Reds / m</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-surface1">
                  {(matchFactors.referees || []).slice(0, 5).map((ref) => (
                    <tr key={ref.referee} className="hover:bg-surface1/30">
                      <td className="py-2 font-medium text-text">{ref.referee}</td>
                      <td className="py-2 text-center text-subtext1">{ref.matches}</td>
                      <td className="py-2 text-right font-mono text-yellow">{ref.yellow_cards_mean?.toFixed(2) ?? '-'}</td>
                      <td className="py-2 text-right font-mono text-red">{ref.red_cards_mean?.toFixed(2) ?? '-'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default function AnalysisPage() {
  return (
    <div className="space-y-6">
      <PageHeader icon={BarChart3} eyebrow="Compare and explain" title="Analysis Lab" description="Compare competitions, form, match factors and disciplinary patterns from one filterable workspace." />

      <Suspense fallback={<LoadingSkeleton lines={8} />}>
        <AnalysisContent />
      </Suspense>
    </div>
  );
}
