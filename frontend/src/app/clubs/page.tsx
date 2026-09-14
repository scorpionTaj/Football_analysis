'use client';

import { Suspense, useMemo, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { api } from '@/lib/api/client';
import { queryKeys } from '@/lib/api/query-keys';
import { useFilterParams } from '@/lib/hooks/use-filter-params';
import { SourceBadge } from '@/components/ui/source-badge';
import { LoadingSkeleton, ErrorMessage, EmptyState } from '@/components/ui/loading';
import { Shield, TrendingUp, Calendar, Trophy, Download, Award, ChevronRight } from 'lucide-react';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  CartesianGrid,
  Legend,
} from 'recharts';

export function ClubLabContent() {
  const filters = useFilterParams();
  const selectedClub = filters.team || 'Arsenal';

  // Fetch all teams to populate the club selector
  const { data: teamData } = useQuery({
    queryKey: queryKeys.teams(),
    queryFn: () => api.teams(),
  });

  const allTeams = useMemo(() => {
    const map = new Map<string, string>();
    for (const t of teamData?.teams || []) {
      map.set(t.name, t.team_id);
    }
    return Array.from(map.entries()).sort((a, b) => a[0].localeCompare(b[0]));
  }, [teamData]);

  // Request analysis for the selected club across all seasons
  const requestBody = useMemo(() => ({
    competitions: [],
    seasons: [],
    teams: [selectedClub],
    venue: null,
    form_window: 5,
  }), [selectedClub]);

  const { data: analysis, isLoading: isAnalysisLoading, error: analysisError, refetch } = useQuery({
    queryKey: queryKeys.analysis(requestBody),
    queryFn: () => api.analysis(requestBody),
    enabled: !!selectedClub,
  });

  // Fetch recent matches for the club
  const { data: matchData, isLoading: isMatchesLoading } = useQuery({
    queryKey: queryKeys.matches({ team: selectedClub, limit: 15 }),
    queryFn: () => api.matches({ team: selectedClub, limit: 15 }),
    enabled: !!selectedClub,
  });

  const seasonsList = useMemo(() => {
    return (analysis?.rankings || []).sort((a, b) => a.season - b.season);
  }, [analysis]);

  // Total stats across seasons
  const totals = useMemo(() => {
    const p = seasonsList.reduce((acc, s) => acc + s.played, 0);
    const w = seasonsList.reduce((acc, s) => acc + s.wins, 0);
    const d = seasonsList.reduce((acc, s) => acc + s.draws, 0);
    const l = seasonsList.reduce((acc, s) => acc + s.losses, 0);
    const pts = seasonsList.reduce((acc, s) => acc + s.points, 0);
    const gf = seasonsList.reduce((acc, s) => acc + s.goals_for, 0);
    const ga = seasonsList.reduce((acc, s) => acc + s.goals_against, 0);
    return {
      played: p,
      wins: w,
      draws: d,
      losses: l,
      points: pts,
      goalsFor: gf,
      goalsAgainst: ga,
      ppg: p > 0 ? (pts / p).toFixed(2) : '0',
      winRate: p > 0 ? ((w / p) * 100).toFixed(1) : '0',
    };
  }, [seasonsList]);

  // Evolution chart data
  const chartData = useMemo(() => {
    return seasonsList.map((s) => ({
      season: `${s.season}/${(s.season + 1).toString().slice(2)}`,
      PPG: Number(s.points_per_game.toFixed(2)),
      Points: s.points,
      GoalsScored: s.goals_for,
      GoalsConceded: s.goals_against,
    }));
  }, [seasonsList]);

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
    const csv = [headers.join(','), ...rows.map((r) => r.join(','))].join('\n');
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

  const matches = matchData?.matches || [];

  return (
    <div className="space-y-6">
      {/* Club Selector Bar */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 rounded-xl bg-surface0 border border-surface1 p-4">
        <div className="flex items-center gap-3">
          <div className="p-2.5 rounded-lg bg-blue/10 text-blue">
            <Shield className="h-5 w-5" />
          </div>
          <div>
            <label className="text-xs font-medium text-subtext0 block">Select Club</label>
            <select
              value={selectedClub}
              onChange={(e) => filters.set({ team: e.target.value })}
              className="mt-0.5 rounded-lg border border-surface1 bg-mantle px-3 py-1.5 text-sm font-semibold text-text outline-none cursor-pointer hover:border-surface2 focus:border-blue"
            >
              {allTeams.map(([name, id]) => (
                <option key={id} value={name}>{name}</option>
              ))}
            </select>
          </div>
        </div>

        <div className="flex items-center gap-3">
          {analysis?.source && <SourceBadge meta={analysis.source} />}
          <button
            onClick={exportCsv}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-mantle border border-surface1 hover:border-surface2 text-xs font-medium text-text transition-colors cursor-pointer"
          >
            <Download className="h-3.5 w-3.5 text-blue" />
            <span>Export History</span>
          </button>
        </div>
      </div>

      {/* Club Overview KPI Grid */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
        <div className="rounded-xl bg-surface0 border border-surface1 p-4">
          <p className="text-xs text-subtext0 uppercase font-medium">Matches (All Seasons)</p>
          <p className="text-2xl font-bold text-text mt-1">{totals.played}</p>
        </div>
        <div className="rounded-xl bg-surface0 border border-surface1 p-4">
          <p className="text-xs text-subtext0 uppercase font-medium">Win Rate</p>
          <p className="text-2xl font-bold text-green mt-1">{totals.winRate}%</p>
        </div>
        <div className="rounded-xl bg-surface0 border border-surface1 p-4">
          <p className="text-xs text-subtext0 uppercase font-medium">Total Points</p>
          <p className="text-2xl font-bold text-blue mt-1">{totals.points}</p>
        </div>
        <div className="rounded-xl bg-surface0 border border-surface1 p-4">
          <p className="text-xs text-subtext0 uppercase font-medium">Overall PPG</p>
          <p className="text-2xl font-bold text-peach mt-1">{totals.ppg}</p>
        </div>
      </div>

      {/* Season Evolution Chart */}
      {chartData.length > 0 && (
        <div className="rounded-xl border border-surface1 bg-surface0 p-5 space-y-4">
          <div className="flex items-center gap-2">
            <TrendingUp className="h-4 w-4 text-blue" />
            <h2 className="text-base font-semibold text-text">{selectedClub} — Performance Trajectory</h2>
          </div>

          <div className="h-72 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={chartData} margin={{ top: 10, right: 20, left: -10, bottom: 5 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#313244" vertical={false} />
                <XAxis dataKey="season" stroke="#7f849c" fontSize={11} />
                <YAxis stroke="#7f849c" fontSize={11} />
                <Tooltip
                  contentStyle={{ backgroundColor: '#181825', borderColor: '#45475a', borderRadius: '8px', color: '#cdd6f4' }}
                />
                <Legend wrapperStyle={{ fontSize: '11px', color: '#bac2de' }} />
                <Line type="monotone" dataKey="Points" stroke="#89b4fa" strokeWidth={2.5} dot={{ fill: '#89b4fa', r: 4 }} />
                <Line type="monotone" dataKey="GoalsScored" stroke="#a6e3a1" strokeWidth={2} dot={{ fill: '#a6e3a1', r: 3 }} />
                <Line type="monotone" dataKey="GoalsConceded" stroke="#f38ba8" strokeWidth={2} dot={{ fill: '#f38ba8', r: 3 }} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}

      {/* Season-by-Season Breakdown Table */}
      <div className="rounded-xl border border-surface1 bg-surface0 overflow-hidden">
        <div className="p-4 border-b border-surface1 flex items-center justify-between">
          <h3 className="text-base font-semibold text-text flex items-center gap-2">
            <Trophy className="h-4 w-4 text-yellow" /> Season History Breakdown
          </h3>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead className="border-b border-surface1 bg-mantle text-xs uppercase text-subtext0">
              <tr>
                <th className="py-3 px-4">Season</th>
                <th className="py-3 px-4">League</th>
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
              {seasonsList.map((s) => (
                <tr key={`${s.competition}_${s.season}`} className="hover:bg-surface1/40 transition-colors">
                  <td className="py-3 px-4 font-mono text-xs font-semibold text-text">
                    {s.season}/{s.season + 1}
                  </td>
                  <td className="py-3 px-4 text-xs text-subtext1">
                    <span className="rounded bg-surface1 px-2 py-0.5">{s.competition}</span>
                  </td>
                  <td className="py-3 px-3 text-center text-subtext1">{s.played}</td>
                  <td className="py-3 px-3 text-center text-green font-medium">{s.wins}</td>
                  <td className="py-3 px-3 text-center text-yellow font-medium">{s.draws}</td>
                  <td className="py-3 px-3 text-center text-red font-medium">{s.losses}</td>
                  <td className="py-3 px-3 text-center text-subtext1">{s.goals_for}</td>
                  <td className="py-3 px-3 text-center text-subtext1">{s.goals_against}</td>
                  <td className={`py-3 px-3 text-center font-mono text-xs font-semibold ${
                    s.goal_difference > 0 ? 'text-green' : s.goal_difference < 0 ? 'text-red' : 'text-subtext0'
                  }`}>
                    {s.goal_difference > 0 ? `+${s.goal_difference}` : s.goal_difference}
                  </td>
                  <td className="py-3 px-3 text-center font-bold text-blue">{s.points}</td>
                  <td className="py-3 px-3 text-right font-mono text-xs">{s.points_per_game.toFixed(2)}</td>
                  <td className="py-3 px-4 text-center">
                    <div className="flex items-center justify-center gap-1">
                      {(s.form || '').split(' ').map((char, ci) => {
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
      </div>

      {/* Recent Match Log for the Club */}
      <div className="rounded-xl border border-surface1 bg-surface0 p-5 space-y-3">
        <h3 className="text-base font-semibold text-text flex items-center gap-2">
          <Calendar className="h-4 w-4 text-teal" /> Recent Club Fixtures
        </h3>

        {isMatchesLoading ? (
          <LoadingSkeleton lines={4} />
        ) : matches.length === 0 ? (
          <EmptyState icon="⚽" message="No recent fixtures recorded for this club." />
        ) : (
          <div className="space-y-2">
            {matches.slice(0, 8).map((m, idx) => {
              const isHome = m.home.name === selectedClub;
              const opponent = isHome ? m.away.name : m.home.name;
              const clubGoals = isHome ? m.home_goals : m.away_goals;
              const oppGoals = isHome ? m.away_goals : m.home_goals;
              const outcome =
                clubGoals !== null && oppGoals !== null
                  ? clubGoals > oppGoals
                    ? 'W'
                    : clubGoals === oppGoals
                    ? 'D'
                    : 'L'
                  : null;

              return (
                <div
                  key={`${m.match_date}_${idx}`}
                  className="flex items-center justify-between p-3 rounded-lg bg-mantle border border-surface1 text-xs"
                >
                  <div className="flex items-center gap-3">
                    <span className="font-mono text-overlay1 text-[11px]">{m.match_date}</span>
                    <span className="rounded bg-surface0 px-2 py-0.5 text-subtext1 font-medium">
                      {isHome ? 'Home' : 'Away'}
                    </span>
                    <span className="font-semibold text-text truncate">vs {opponent}</span>
                  </div>

                  <div className="flex items-center gap-3">
                    <span className="font-mono font-bold text-text">
                      {m.home_goals} - {m.away_goals}
                    </span>
                    {outcome && (
                      <span
                        className={`h-5 w-5 rounded font-bold text-[10px] flex items-center justify-center ${
                          outcome === 'W'
                            ? 'bg-green/20 text-green'
                            : outcome === 'D'
                            ? 'bg-yellow/20 text-yellow'
                            : 'bg-red/20 text-red'
                        }`}
                      >
                        {outcome}
                      </span>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}

export default function ClubsPage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-text tracking-tight">Club Lab</h1>
        <p className="text-sm text-subtext0 mt-1">
          Deep-dive club performance profiling, historical season trajectories, and fixture breakdowns.
        </p>
      </div>

      <Suspense fallback={<LoadingSkeleton lines={10} />}>
        <ClubLabContent />
      </Suspense>
    </div>
  );
}
