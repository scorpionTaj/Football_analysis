'use client';

import { useMemo, useState } from 'react';
import {
  CartesianGrid, Cell, Legend, Line, LineChart, ResponsiveContainer, Scatter, ScatterChart,
  Tooltip as RechartsTooltip, XAxis, YAxis, ZAxis,
} from 'recharts';
import { FootballBadge } from '@/lib/media-utils';
import type { Competition, OverviewResponse } from '@/lib/api/types';
import { axisProps, gridProps, tooltipProps } from '@/lib/chart-theme';
import { Panel } from '@/components/ui/panel';
import { Segmented } from '@/components/ui/segmented';
import { DataTable, TBody, THead, Td, Th } from '@/components/ui/data-table';

const CHART_VIEWS = [
  { value: 'trend', label: 'Over time' },
  { value: 'matrix', label: 'Strength map' },
  { value: 'scatter', label: 'Attack vs defence' },
  { value: 'elo', label: 'Season-end Elo' },
] as const;

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
      <Panel
        title="Performance analytics"
        description={`Comparative metrics across ${currentComp?.name || selectedComp} seasons`}
        actions={<Segmented label="Chart view" value={chartView} onChange={setChartView} options={CHART_VIEWS} />}
      >
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
                  <CartesianGrid {...gridProps} vertical={false} />
                  <XAxis dataKey="season" {...axisProps} />
                  <YAxis domain={[0, 3]} {...axisProps} />
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
          <DataTable minWidth={560} caption="Season strength map: points per game">
              <THead>
                <tr>
                  <Th>Club</Th>
                  {matrixData.seasons.map((yr) => (
                    <Th key={yr} align="center">
                      {selectedComp === 'WC' ? `${yr}` : `${yr}/${String(yr + 1).slice(-2)}`}
                    </Th>
                  ))}
                </tr>
              </THead>
              <TBody>
                {matrixData.clubs.map((row) => (
                  <tr key={row.club}>
                    <Td>
                      <span className="flex items-center gap-2">
                        <FootballBadge name={row.club} size={20} />
                        <span className={row.club === activeClub ? 'font-semibold text-accent' : ''}>{row.club}</span>
                      </span>
                    </Td>
                    {matrixData.seasons.map((yr) => {
                      const ppg = row.values[yr];
                      // Single-hue sequential scale: stronger accent tint = more points per game.
                      let bgClass = 'text-overlay0';
                      if (ppg !== undefined) {
                        if (ppg >= 2.2) bgClass = 'bg-accent/30 text-text font-semibold';
                        else if (ppg >= 1.8) bgClass = 'bg-accent/20 text-text';
                        else if (ppg >= 1.4) bgClass = 'bg-accent/10 text-text';
                        else bgClass = 'text-subtext0';
                      }

                      return (
                        <Td key={yr} align="center">
                          <span className={`inline-block min-w-12 rounded-md px-2 py-1 text-xs ${bgClass}`}>
                            {ppg !== undefined ? ppg.toFixed(2) : '—'}
                          </span>
                        </Td>
                      );
                    })}
                  </tr>
                ))}
              </TBody>
          </DataTable>
        )}

        {/* View 3: Attacking Output vs Defensive Control (Scatter Plot) */}
        {chartView === 'scatter' && (
          <div>
            <div className="flex items-center justify-between mb-4">
              <span className="text-xs text-subtext0">
                Goals Scored per Match (X) vs Conceded per Match (Y, reversed). Bubble size = PPG.
              </span>
              <span className="text-xs tabular-nums text-subtext0">
                Top-right quadrant = High attack & Low conceded
              </span>
            </div>
            <div className="h-80 w-full">
              <ResponsiveContainer width="100%" height="100%">
                <ScatterChart margin={{ top: 10, right: 30, left: -10, bottom: 20 }}>
                  <CartesianGrid {...gridProps} />
                  <XAxis
                    type="number"
                    dataKey="goalsPerMatch"
                    name="Goals Scored"
                    unit=" G/M"
                    {...axisProps}
                  />
                  <YAxis
                    type="number"
                    dataKey="concededPerMatch"
                    name="Goals Conceded"
                    unit=" G/M"
                    reversed
                    {...axisProps}
                  />
                  <ZAxis type="number" dataKey="ppg" range={[60, 400]} name="PPG" />
                  <RechartsTooltip
                    cursor={{ strokeDasharray: '3 3' }}
                    content={({ payload }) => {
                      if (!payload || !payload.length) return null;
                      const data = payload[0].payload;
                      return (
                        <div className="space-y-0.5 rounded-lg border border-surface1 bg-mantle px-2.5 py-2 text-xs shadow-lg shadow-crust/30">
                          <p className="text-[13px] font-semibold text-text">{data.club}</p>
                          <p className="text-subtext1">Goals scored: {data.goalsPerMatch} / match</p>
                          <p className="text-subtext1">Goals conceded: {data.concededPerMatch} / match</p>
                          <p className="font-semibold text-text">PPG: {data.ppg}</p>
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
                  <CartesianGrid {...gridProps} vertical={false} />
                  <XAxis dataKey="season" {...axisProps} />
                  <YAxis domain={['auto', 'auto']} {...axisProps} />
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
      </Panel>
    </>
  );
}
