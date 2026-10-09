'use client';

import { useMemo, useState } from 'react';
import { Card } from '@heroui/react';
import { TrendingUp } from 'lucide-react';
import {
  CartesianGrid, Cell, Legend, Line, LineChart, ResponsiveContainer, Scatter, ScatterChart,
  Tooltip as RechartsTooltip, XAxis, YAxis, ZAxis,
} from 'recharts';
import { FootballBadge } from '@/lib/media-utils';
import type { Competition, OverviewResponse } from '@/lib/api/types';
import { tooltipProps } from '@/lib/chart-theme';

const CHART_COLORS = [
  'var(--series-1)', // blue
  'var(--green)', // green
  'var(--series-2)', // peach
  'var(--red)', // red
  'var(--series-3)', // mauve
  'var(--teal)', // teal
  'var(--yellow)', // yellow
  'var(--sapphire)', // sapphire
];

/**
 * Club trends on the Overview: PPG over time, season strength map, attack vs defence and Elo.
 * Owns the chart-tab state, so switching tabs re-renders only this section.
 */
export function ClubTrends({
  overviewData, selectedComp, selectedSeason, availableSeasons, activeClub, currentComp,
}: {
  overviewData: OverviewResponse | undefined;
  selectedComp: string;
  selectedSeason: number;
  availableSeasons: number[];
  activeClub: string;
  currentComp: Competition | undefined;
}) {
  const [chartView, setChartView] = useState<'trend' | 'matrix' | 'scatter' | 'elo'>('trend');

  // -------------------------------------------------------------
  // Chart Data Preparations
  // -------------------------------------------------------------

  // Top 5 clubs in the current league by points in latest season for cleaner charts
  const topClubs = useMemo(() => {
    if (!overviewData?.performance_over_time) return [];
    const latestSeasonRows = overviewData.performance_over_time
      .filter((r) => r.competition === selectedComp && r.season === selectedSeason)
      .sort((a, b) => b.points - a.points);
    const topNames = new Set(latestSeasonRows.slice(0, 5).map((r) => r.team.name));
    if (activeClub) topNames.add(activeClub);
    return Array.from(topNames);
  }, [overviewData, selectedComp, selectedSeason, activeClub]);

  // Performance Over Time (PPG Line Chart Data)
  const trendChartData = useMemo(() => {
    if (!overviewData?.performance_over_time) return [];
    const bySeason = new Map<number, Record<string, number | string>>();
    const seasonsList = [...availableSeasons].sort((a, b) => a - b);

    for (const yr of seasonsList) {
      const yrLabel = `${yr}/${String(yr + 1).slice(-2)}`;
      bySeason.set(yr, { season: yrLabel });
    }

    for (const r of overviewData.performance_over_time) {
      if (r.competition === selectedComp && topClubs.includes(r.team.name)) {
        const item = bySeason.get(r.season);
        if (item) {
          item[r.team.name] = Number(r.points_per_game.toFixed(2));
        }
      }
    }
    return Array.from(bySeason.values());
  }, [overviewData, selectedComp, topClubs, availableSeasons]);

  // Season Strength Matrix (Heatmap Table Data)
  const matrixData = useMemo(() => {
    if (!overviewData?.performance_over_time) {
      return {
        seasons: [] as number[],
        clubs: [] as { club: string; values: Record<number, number> }[],
      };
    }
    const clubRows = new Map<string, Record<number, number>>();
    const seasonsList = [...availableSeasons].sort((a, b) => a - b);

    for (const r of overviewData.performance_over_time) {
      if (r.competition === selectedComp && topClubs.includes(r.team.name)) {
        if (!clubRows.has(r.team.name)) {
          clubRows.set(r.team.name, {});
        }
        clubRows.get(r.team.name)![r.season] = r.points_per_game;
      }
    }

    return {
      seasons: seasonsList,
      clubs: Array.from(clubRows.entries()).map(([club, values]) => ({
        club,
        values,
      })),
    };
  }, [overviewData, selectedComp, topClubs, availableSeasons]);

  // Attacking Output vs Defensive Control (Scatter Chart Data)
  const scatterData = useMemo(() => {
    if (!overviewData?.performance_over_time) return [];
    const clubAgg = new Map<string, { played: number; gf: number; ga: number; points: number }>();

    for (const r of overviewData.performance_over_time) {
      if (r.competition === selectedComp) {
        const current = clubAgg.get(r.team.name) || { played: 0, gf: 0, ga: 0, points: 0 };
        current.played += r.played;
        current.gf += r.goals_for;
        current.ga += r.goals_against;
        current.points += r.points;
        clubAgg.set(r.team.name, current);
      }
    }

    return Array.from(clubAgg.entries())
      .filter(([, stats]) => stats.played > 0)
      .map(([club, stats]) => {
        const goalsPerMatch = Number((stats.gf / stats.played).toFixed(2));
        const concededPerMatch = Number((stats.ga / stats.played).toFixed(2));
        const ppg = Number((stats.points / stats.played).toFixed(2));
        return {
          club,
          goalsPerMatch,
          concededPerMatch,
          ppg,
          played: stats.played,
        };
      });
  }, [overviewData, selectedComp]);

  // Opponent-Adjusted Elo Trajectory Data
  const eloChartData = useMemo(() => {
    if (!overviewData?.elo_trajectory) return [];
    const bySeason = new Map<number, Record<string, number | string>>();
    const seasonsList = [...availableSeasons].sort((a, b) => a - b);

    for (const yr of seasonsList) {
      const yrLabel = `${yr}/${String(yr + 1).slice(-2)}`;
      bySeason.set(yr, { season: yrLabel });
    }

    for (const er of overviewData.elo_trajectory) {
      if (er.league === selectedComp && topClubs.includes(er.team.name)) {
        const item = bySeason.get(er.season);
        if (item) {
          item[er.team.name] = Math.round(er.post_elo);
        }
      }
    }
    return Array.from(bySeason.values());
  }, [overviewData, selectedComp, topClubs, availableSeasons]);

  return (
    <>
      {/* 5. Analytics Visualizations */}
      <Card className="rounded-2xl bg-surface0 border border-surface1/80 p-6 shadow-sm">
        <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4 border-b border-surface1/60 pb-4 mb-6">
          <div>
            <h2 className="text-lg font-bold text-text flex items-center gap-2">
              <TrendingUp size={18} className="text-blue" />
              Advanced Performance Analytics
            </h2>
            <p className="text-xs text-subtext0">
              Comparative metrics across {currentComp?.name || selectedComp} seasons
            </p>
          </div>

          {/* Visualization Tab Switcher */}
          <div className="flex flex-wrap items-center gap-1.5 p-1 bg-mantle rounded-xl border border-surface1 text-xs">
            <button
              onClick={() => setChartView('trend')}
              className={`px-3 py-1.5 rounded-lg font-semibold transition-colors cursor-pointer ${
                chartView === 'trend'
                  ? 'bg-base text-blue shadow-sm'
                  : 'text-subtext0 hover:text-text'
              }`}
            >
              Performance Over Time
            </button>
            <button
              onClick={() => setChartView('matrix')}
              className={`px-3 py-1.5 rounded-lg font-semibold transition-colors cursor-pointer ${
                chartView === 'matrix'
                  ? 'bg-base text-blue shadow-sm'
                  : 'text-subtext0 hover:text-text'
              }`}
            >
              Season Strength Map
            </button>
            <button
              onClick={() => setChartView('scatter')}
              className={`px-3 py-1.5 rounded-lg font-semibold transition-colors cursor-pointer ${
                chartView === 'scatter'
                  ? 'bg-base text-blue shadow-sm'
                  : 'text-subtext0 hover:text-text'
              }`}
            >
              Attack vs Defense
            </button>
            <button
              onClick={() => setChartView('elo')}
              className={`px-3 py-1.5 rounded-lg font-semibold transition-colors cursor-pointer ${
                chartView === 'elo'
                  ? 'bg-base text-blue shadow-sm'
                  : 'text-subtext0 hover:text-text'
              }`}
            >
              Season-End Elo
            </button>
          </div>
        </div>

        {/* View 1: Performance Over Time (PPG Line Chart) */}
        {chartView === 'trend' && (
          <div>
            <div className="flex items-center justify-between mb-4">
              <span className="text-xs text-subtext0">
                Points per Game (PPG) trajectory across seasons for top clubs
              </span>
              <span className="text-[11px] font-mono text-overlay1">
                Y-Axis: PPG (0.0 – 3.0)
              </span>
            </div>
            <div className="h-80 w-full">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={trendChartData} margin={{ top: 10, right: 20, left: -15, bottom: 5 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="var(--chart-grid)" vertical={false} />
                  <XAxis dataKey="season" stroke="var(--chart-axis)" fontSize={12} />
                  <YAxis domain={[0, 3]} stroke="var(--chart-axis)" fontSize={12} />
                  <RechartsTooltip
                    {...tooltipProps}
                  />
                  <Legend wrapperStyle={{ paddingTop: '10px', fontSize: '12px' }} />
                  {topClubs.map((club, idx) => (
                    <Line
                      key={club}
                      type="monotone"
                      dataKey={club}
                      stroke={CHART_COLORS[idx % CHART_COLORS.length]}
                      strokeWidth={club === activeClub ? 4 : 2}
                      dot={{ r: club === activeClub ? 5 : 3 }}
                      activeDot={{ r: 7 }}
                    />
                  ))}
                </LineChart>
              </ResponsiveContainer>
            </div>
          </div>
        )}

        {/* View 2: Season Strength Map (Matrix / Heatmap) */}
        {chartView === 'matrix' && (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs border-collapse">
              <thead>
                <tr className="border-b border-surface1 bg-mantle text-subtext0 uppercase tracking-wider">
                  <th className="py-3 px-4 font-bold">Club</th>
                  {matrixData.seasons.map((yr) => (
                    <th key={yr} className="py-3 px-3 text-center font-bold">
                      {selectedComp === 'WC' ? `${yr}` : `${yr}/${String(yr + 1).slice(-2)}`}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-surface1">
                {matrixData.clubs.map((row) => (
                  <tr key={row.club} className="hover:bg-surface1/30 transition-colors">
                    <td className="py-3 px-4 font-semibold text-text flex items-center gap-2">
                      <FootballBadge name={row.club} size={20} />
                      <span className={row.club === activeClub ? 'text-blue font-bold' : ''}>
                        {row.club}
                      </span>
                    </td>
                    {matrixData.seasons.map((yr) => {
                      const ppg = row.values[yr];
                      let bgClass = 'bg-surface0 text-overlay0';
                      if (ppg !== undefined) {
                        if (ppg >= 2.2) bgClass = 'bg-teal/30 text-teal font-bold border border-teal/40';
                        else if (ppg >= 1.8) bgClass = 'bg-blue/25 text-blue font-semibold border border-blue/30';
                        else if (ppg >= 1.4) bgClass = 'bg-yellow/20 text-yellow border border-yellow/25';
                        else if (ppg >= 1.0) bgClass = 'bg-peach/20 text-peach border border-peach/25';
                        else bgClass = 'bg-red/20 text-red border border-red/25';
                      }

                      return (
                        <td key={yr} className="py-3 px-3 text-center">
                          <span className={`inline-block px-2.5 py-1 rounded-md text-xs font-mono ${bgClass}`}>
                            {ppg !== undefined ? ppg.toFixed(2) : '—'}
                          </span>
                        </td>
                      );
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {/* View 3: Attacking Output vs Defensive Control (Scatter Plot) */}
        {chartView === 'scatter' && (
          <div>
            <div className="flex items-center justify-between mb-4">
              <span className="text-xs text-subtext0">
                Goals Scored per Match (X) vs Conceded per Match (Y, reversed). Bubble size = PPG.
              </span>
              <span className="text-[11px] font-mono text-green">
                Top-right quadrant = High attack & Low conceded
              </span>
            </div>
            <div className="h-80 w-full">
              <ResponsiveContainer width="100%" height="100%">
                <ScatterChart margin={{ top: 10, right: 30, left: -10, bottom: 20 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="var(--chart-grid)" />
                  <XAxis
                    type="number"
                    dataKey="goalsPerMatch"
                    name="Goals Scored"
                    unit=" G/M"
                    stroke="var(--chart-axis)"
                    fontSize={12}
                  />
                  <YAxis
                    type="number"
                    dataKey="concededPerMatch"
                    name="Goals Conceded"
                    unit=" G/M"
                    reversed
                    stroke="var(--chart-axis)"
                    fontSize={12}
                  />
                  <ZAxis type="number" dataKey="ppg" range={[60, 400]} name="PPG" />
                  <RechartsTooltip
                    cursor={{ strokeDasharray: '3 3' }}
                    content={({ payload }) => {
                      if (!payload || !payload.length) return null;
                      const data = payload[0].payload;
                      return (
                        <div className="p-3 rounded-xl bg-mantle border border-surface1 shadow-xl text-xs space-y-1">
                          <p className="font-bold text-text text-sm">{data.club}</p>
                          <p className="text-green">Goals Scored: {data.goalsPerMatch} / match</p>
                          <p className="text-red">Goals Conceded: {data.concededPerMatch} / match</p>
                          <p className="text-blue font-bold">PPG: {data.ppg}</p>
                          <p className="text-overlay1">Matches: {data.played}</p>
                        </div>
                      );
                    }}
                  />
                  <Scatter name="Clubs" data={scatterData}>
                    {scatterData.map((entry, index) => (
                      <Cell
                        key={`cell-${index}`}
                        fill={entry.club === activeClub ? 'var(--series-1)' : entry.ppg >= 2.0 ? 'var(--teal)' : 'var(--red)'}
                        stroke="var(--text)"
                        strokeWidth={entry.club === activeClub ? 2 : 0}
                      />
                    ))}
                  </Scatter>
                </ScatterChart>
              </ResponsiveContainer>
            </div>
          </div>
        )}

        {/* View 4: Opponent-Adjusted Season-End Elo */}
        {chartView === 'elo' && (
          <div>
            <div className="flex items-center justify-between mb-4">
              <span className="text-xs text-subtext0">
                Opponent-adjusted season-end Elo progression across domestic seasons
              </span>
              <span className="text-[11px] font-mono text-overlay1">
                Calibrated per domestic league
              </span>
            </div>
            <div className="h-80 w-full">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={eloChartData} margin={{ top: 10, right: 20, left: -5, bottom: 5 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="var(--chart-grid)" vertical={false} />
                  <XAxis dataKey="season" stroke="var(--chart-axis)" fontSize={12} />
                  <YAxis domain={['auto', 'auto']} stroke="var(--chart-axis)" fontSize={12} />
                  <RechartsTooltip
                    {...tooltipProps}
                  />
                  <Legend wrapperStyle={{ paddingTop: '10px', fontSize: '12px' }} />
                  {topClubs.map((club, idx) => (
                    <Line
                      key={club}
                      type="monotone"
                      dataKey={club}
                      stroke={CHART_COLORS[idx % CHART_COLORS.length]}
                      strokeWidth={club === activeClub ? 4 : 2}
                      dot={{ r: club === activeClub ? 5 : 3 }}
                      activeDot={{ r: 7 }}
                    />
                  ))}
                </LineChart>
              </ResponsiveContainer>
            </div>
          </div>
        )}
      </Card>
    </>
  );
}
