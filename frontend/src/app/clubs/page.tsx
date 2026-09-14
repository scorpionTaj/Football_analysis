'use client';

import { Suspense, useMemo, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { api } from '@/lib/api/client';
import { queryKeys } from '@/lib/api/query-keys';
import { useFilterParams } from '@/lib/hooks/use-filter-params';
import { SourceBadge } from '@/components/ui/source-badge';
import { LoadingSkeleton, ErrorMessage, EmptyState } from '@/components/ui/loading';
import { Shield, TrendingUp, Calendar, Trophy, Download, Swords, ChevronRight, BarChart2 } from 'lucide-react';
import { usePagination } from '@/components/ui/pagination';
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
  const [activeTab, setActiveTab] = useState<'profile' | 'h2h'>('profile');
  const [opponentClub, setOpponentClub] = useState<string>('Chelsea');

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
  const { data: matchData, isLoading: isMatchesLoading } = useQuery({
    queryKey: queryKeys.matches({ team: selectedClub, limit: 100 }),
    queryFn: () => api.matches({ team: selectedClub, limit: 100 }),
    enabled: !!selectedClub,
  });

  // Fetch fixtures for opponent club if in H2H mode
  const { data: opponentMatchData } = useQuery({
    queryKey: queryKeys.matches({ team: opponentClub, limit: 100 }),
    queryFn: () => api.matches({ team: opponentClub, limit: 100 }),
    enabled: activeTab === 'h2h' && !!opponentClub,
  });

  const seasonsList = useMemo(() => {
    return (analysis?.rankings || []).sort((a, b) => a.season - b.season);
  }, [analysis]);

  // Paginated season history table (10 per page)
  const { paginatedItems: paginatedSeasons, PaginationComponent: SeasonsPagination } = usePagination(seasonsList, 10);

  // Total stats across seasons for selected club
  const totals = useMemo(() => {
    const p = seasonsList.reduce((acc, s) => acc + s.played, 0);
    const w = seasonsList.reduce((acc, s) => acc + s.wins, 0);
    const d = seasonsList.reduce((acc, s) => acc + s.draws, 0);
    const l = seasonsList.reduce((acc, s) => acc + s.losses, 0);
    const pts = seasonsList.reduce((acc, s) => acc + s.points, 0);
    const gf = seasonsList.reduce((acc, s) => acc + s.goals_for, 0);
    const ga = seasonsList.reduce((acc, s) => acc + s.goals_against, 0);
    const csWeighted = seasonsList.reduce((acc, s) => acc + (s.clean_sheet_rate * s.played), 0);
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
      gfPerMatch: p > 0 ? (gf / p).toFixed(2) : '0',
      gaPerMatch: p > 0 ? (ga / p).toFixed(2) : '0',
      cleanSheetRate: p > 0 ? (csWeighted / p).toFixed(1) : '0',
    };
  }, [seasonsList]);

  // Total stats across seasons for opponent club
  const opponentTotals = useMemo(() => {
    const oppSeasons = opponentAnalysis?.rankings || [];
    const p = oppSeasons.reduce((acc, s) => acc + s.played, 0);
    const w = oppSeasons.reduce((acc, s) => acc + s.wins, 0);
    const d = oppSeasons.reduce((acc, s) => acc + s.draws, 0);
    const l = oppSeasons.reduce((acc, s) => acc + s.losses, 0);
    const pts = oppSeasons.reduce((acc, s) => acc + s.points, 0);
    const gf = oppSeasons.reduce((acc, s) => acc + s.goals_for, 0);
    const ga = oppSeasons.reduce((acc, s) => acc + s.goals_against, 0);
    const oppCsWeighted = oppSeasons.reduce((acc, s) => acc + (s.clean_sheet_rate * s.played), 0);
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
      gfPerMatch: p > 0 ? (gf / p).toFixed(2) : '0',
      gaPerMatch: p > 0 ? (ga / p).toFixed(2) : '0',
      cleanSheetRate: p > 0 ? (oppCsWeighted / p).toFixed(1) : '0',
    };
  }, [opponentAnalysis?.rankings]);

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

  const matches = matchData?.matches || [];
  // Paginated club recent fixtures (10 per page)
  const { paginatedItems: paginatedMatches, PaginationComponent: MatchesPagination } = usePagination(matches, 10);

  // Head-to-Head matches calculation
  const h2hMatches = useMemo(() => {
    const combined = [...(matchData?.matches || []), ...(opponentMatchData?.matches || [])].filter((m) =>
      (m.home.name === selectedClub && m.away.name === opponentClub) ||
      (m.home.name === opponentClub && m.away.name === selectedClub)
    );
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
  }, [matchData?.matches, opponentMatchData?.matches, selectedClub, opponentClub]);

  // Paginated Head-to-Head encounters (10 per page)
  const { paginatedItems: paginatedH2HMatches, PaginationComponent: H2HPagination } = usePagination(h2hMatches, 10);

  const h2hStats = useMemo(() => {
    let clubAWins = 0;
    let clubBWins = 0;
    let draws = 0;
    let clubAGoals = 0;
    let clubBGoals = 0;

    for (const m of h2hMatches) {
      if (m.home_goals === null || m.away_goals === null) continue;
      const isHomeA = m.home.name === selectedClub;
      const aGoals = isHomeA ? m.home_goals : m.away_goals;
      const bGoals = isHomeA ? m.away_goals : m.home_goals;

      clubAGoals += aGoals;
      clubBGoals += bGoals;
      if (aGoals > bGoals) clubAWins++;
      else if (bGoals > aGoals) clubBWins++;
      else draws++;
    }

    return {
      clashes: h2hMatches.length,
      clubAWins,
      clubBWins,
      draws,
      clubAGoals,
      clubBGoals,
    };
  }, [h2hMatches, selectedClub, opponentClub]);

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

  return (
    <div className="space-y-6">
      {/* Club Selector Bar */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 rounded-xl bg-surface0 border border-surface1 p-4">
        <div className="flex flex-wrap items-center gap-3">
          <div className="p-2.5 rounded-lg bg-blue/10 text-blue">
            <Shield className="h-5 w-5" />
          </div>
          <div>
            <label className="text-xs font-medium text-subtext0 block">Primary Club</label>
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

          {activeTab === 'h2h' && (
            <>
              <div className="text-overlay0 font-bold px-1 text-sm">VS</div>
              <div>
                <label className="text-xs font-medium text-subtext0 block">Opponent Club</label>
                <select
                  value={opponentClub}
                  onChange={(e) => setOpponentClub(e.target.value)}
                  className="mt-0.5 rounded-lg border border-surface1 bg-mantle px-3 py-1.5 text-sm font-semibold text-text outline-none cursor-pointer hover:border-surface2 focus:border-blue"
                >
                  {allTeams.map(([name, id]) => (
                    <option key={id} value={name}>{name}</option>
                  ))}
                </select>
              </div>
            </>
          )}
        </div>

        <div className="flex flex-wrap items-center gap-2">
          {/* Tab switcher */}
          <div className="flex items-center bg-mantle rounded-lg p-1 border border-surface1">
            <button
              onClick={() => setActiveTab('profile')}
              className={`flex items-center gap-1.5 px-3 py-1 rounded-md text-xs font-medium transition-colors ${
                activeTab === 'profile'
                  ? 'bg-blue text-mantle font-semibold shadow-sm'
                  : 'text-subtext0 hover:text-text'
              }`}
            >
              <BarChart2 className="h-3.5 w-3.5" />
              <span>Club Profile</span>
            </button>
            <button
              onClick={() => setActiveTab('h2h')}
              className={`flex items-center gap-1.5 px-3 py-1 rounded-md text-xs font-medium transition-colors ${
                activeTab === 'h2h'
                  ? 'bg-blue text-mantle font-semibold shadow-sm'
                  : 'text-subtext0 hover:text-text'
              }`}
            >
              <Swords className="h-3.5 w-3.5" />
              <span>Head-to-Head</span>
            </button>
          </div>

          {analysis?.source && <SourceBadge meta={analysis.source} />}
          <button
            onClick={exportCsv}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-mantle border border-surface1 hover:border-surface2 text-xs font-medium text-text transition-colors cursor-pointer"
          >
            <Download className="h-3.5 w-3.5 text-blue" />
            <span>Export</span>
          </button>
        </div>
      </div>

      {activeTab === 'profile' ? (
        <>
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

          {/* Season-by-Season Breakdown Table (Paginated: 10 per page) */}
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
                  {paginatedSeasons.map((s) => (
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
            <div className="px-4 py-3 bg-mantle border-t border-surface1">
              <SeasonsPagination />
            </div>
          </div>

          {/* Recent Match Log for the Club (Paginated: 10 per page) */}
          <div className="rounded-xl border border-surface1 bg-surface0 p-5 space-y-4">
            <h3 className="text-base font-semibold text-text flex items-center gap-2">
              <Calendar className="h-4 w-4 text-teal" /> Recent Club Fixtures
            </h3>

            {isMatchesLoading ? (
              <LoadingSkeleton lines={4} />
            ) : matches.length === 0 ? (
              <EmptyState icon="⚽" message="No recent fixtures recorded for this club." />
            ) : (
              <div className="space-y-3">
                <div className="space-y-2">
                  {paginatedMatches.map((m, idx) => {
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
                <div className="pt-2 border-t border-surface1">
                  <MatchesPagination />
                </div>
              </div>
            )}
          </div>
        </>
      ) : (
        /* Head-to-Head Comparison View */
        <div className="space-y-6">
          {/* Head-to-Head Hero Summary Card */}
          <div className="rounded-xl border border-surface1 bg-surface0 p-6">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-6">
              {/* Club A */}
              <div className="flex items-center gap-4 text-left">
                <div className="h-14 w-14 rounded-2xl bg-blue/15 text-blue flex items-center justify-center font-bold text-xl border border-blue/20">
                  {selectedClub.slice(0, 2).toUpperCase()}
                </div>
                <div>
                  <h3 className="text-lg font-bold text-text">{selectedClub}</h3>
                  <p className="text-xs text-subtext0">Primary Club</p>
                  <p className="text-xl font-bold text-blue mt-1">{h2hStats.clubAWins} wins</p>
                </div>
              </div>

              {/* Direct Clash Summary Badge */}
              <div className="text-center px-4 py-3 rounded-xl bg-mantle border border-surface1 min-w-[140px]">
                <p className="text-xs font-semibold text-subtext0 uppercase tracking-wider">Direct Clashes</p>
                <p className="text-3xl font-extrabold text-text mt-1">{h2hStats.clashes}</p>
                <p className="text-xs text-yellow font-medium mt-0.5">{h2hStats.draws} Draws</p>
              </div>

              {/* Club B */}
              <div className="flex items-center gap-4 text-right sm:flex-row-reverse">
                <div className="h-14 w-14 rounded-2xl bg-peach/15 text-peach flex items-center justify-center font-bold text-xl border border-peach/20">
                  {opponentClub.slice(0, 2).toUpperCase()}
                </div>
                <div>
                  <h3 className="text-lg font-bold text-text">{opponentClub}</h3>
                  <p className="text-xs text-subtext0">Opponent</p>
                  <p className="text-xl font-bold text-peach mt-1">{h2hStats.clubBWins} wins</p>
                </div>
              </div>
            </div>

            {/* Total Goals Bar */}
            <div className="mt-6 pt-5 border-t border-surface1">
              <div className="flex items-center justify-between text-xs font-semibold mb-1.5">
                <span className="text-blue">{selectedClub}: {h2hStats.clubAGoals} goals</span>
                <span className="text-subtext0 uppercase text-[11px]">H2H Goals Scored</span>
                <span className="text-peach">{opponentClub}: {h2hStats.clubBGoals} goals</span>
              </div>
              <div className="w-full bg-mantle h-2.5 rounded-full overflow-hidden flex">
                <div
                  className="bg-blue transition-all duration-500"
                  style={{
                    width: `${
                      h2hStats.clubAGoals + h2hStats.clubBGoals > 0
                        ? (h2hStats.clubAGoals / (h2hStats.clubAGoals + h2hStats.clubBGoals)) * 100
                        : 50
                    }%`,
                  }}
                />
                <div
                  className="bg-peach transition-all duration-500"
                  style={{
                    width: `${
                      h2hStats.clubAGoals + h2hStats.clubBGoals > 0
                        ? (h2hStats.clubBGoals / (h2hStats.clubAGoals + h2hStats.clubBGoals)) * 100
                        : 50
                    }%`,
                  }}
                />
              </div>
            </div>
          </div>

          {/* Comparative Benchmarking Metrics */}
          <div className="rounded-xl border border-surface1 bg-surface0 p-5 space-y-4">
            <h3 className="text-base font-semibold text-text flex items-center gap-2">
              <BarChart2 className="h-4 w-4 text-blue" /> Overall Performance Benchmark Comparison
            </h3>

            <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-4">
              <div className="rounded-lg bg-mantle p-3 border border-surface1">
                <p className="text-xs text-subtext0 uppercase">Points Per Game</p>
                <div className="flex items-center justify-between mt-2 text-sm font-bold">
                  <span className="text-blue">{totals.ppg}</span>
                  <span className="text-overlay0 text-xs font-normal">vs</span>
                  <span className="text-peach">{opponentTotals.ppg}</span>
                </div>
              </div>

              <div className="rounded-lg bg-mantle p-3 border border-surface1">
                <p className="text-xs text-subtext0 uppercase">Win Rate</p>
                <div className="flex items-center justify-between mt-2 text-sm font-bold">
                  <span className="text-blue">{totals.winRate}%</span>
                  <span className="text-overlay0 text-xs font-normal">vs</span>
                  <span className="text-peach">{opponentTotals.winRate}%</span>
                </div>
              </div>

              <div className="rounded-lg bg-mantle p-3 border border-surface1">
                <p className="text-xs text-subtext0 uppercase">Goals / Match</p>
                <div className="flex items-center justify-between mt-2 text-sm font-bold">
                  <span className="text-blue">{totals.gfPerMatch}</span>
                  <span className="text-overlay0 text-xs font-normal">vs</span>
                  <span className="text-peach">{opponentTotals.gfPerMatch}</span>
                </div>
              </div>

              <div className="rounded-lg bg-mantle p-3 border border-surface1">
                <p className="text-xs text-subtext0 uppercase">Clean Sheet %</p>
                <div className="flex items-center justify-between mt-2 text-sm font-bold">
                  <span className="text-blue">{totals.cleanSheetRate}%</span>
                  <span className="text-overlay0 text-xs font-normal">vs</span>
                  <span className="text-peach">{opponentTotals.cleanSheetRate}%</span>
                </div>
              </div>
            </div>
          </div>

          {/* Direct Encounters Fixture List (Paginated: 10 per page) */}
          <div className="rounded-xl border border-surface1 bg-surface0 p-5 space-y-4">
            <h3 className="text-base font-semibold text-text flex items-center gap-2">
              <Calendar className="h-4 w-4 text-teal" /> Historical Direct Encounters ({h2hMatches.length})
            </h3>

            {h2hMatches.length === 0 ? (
              <EmptyState
                icon="⚽"
                message={`No direct matches found between ${selectedClub} and ${opponentClub} in covered fixtures.`}
                suggestion="Select two clubs from the same domestic league to view historical clashes."
              />
            ) : (
              <div className="space-y-3">
                <div className="space-y-2">
                  {paginatedH2HMatches.map((m, idx) => {
                    const isHomeA = m.home.name === selectedClub;
                    const clubAGoals = isHomeA ? m.home_goals : m.away_goals;
                    const clubBGoals = isHomeA ? m.away_goals : m.home_goals;
                    const winner =
                      clubAGoals !== null && clubBGoals !== null
                        ? clubAGoals > clubBGoals
                          ? selectedClub
                          : clubBGoals > clubAGoals
                          ? opponentClub
                          : 'Draw'
                        : null;

                    return (
                      <div
                        key={`${m.match_date}_${idx}`}
                        className="flex flex-col sm:flex-row sm:items-center justify-between p-3.5 rounded-lg bg-mantle border border-surface1 gap-2 text-xs"
                      >
                        <div className="flex items-center gap-3">
                          <span className="font-mono text-overlay1 text-[11px]">{m.match_date}</span>
                          <span className="rounded bg-surface0 px-2 py-0.5 text-subtext1 font-medium">
                            {m.competition}
                          </span>
                          <span className="text-subtext0">
                            {m.home.name} (H) vs {m.away.name} (A)
                          </span>
                        </div>

                        <div className="flex items-center gap-4 self-end sm:self-auto">
                          <span className="font-mono text-sm font-bold text-text">
                            {m.home_goals} - {m.away_goals}
                          </span>
                          {winner && (
                            <span
                              className={`px-2.5 py-0.5 rounded-full text-[11px] font-semibold ${
                                winner === selectedClub
                                  ? 'bg-blue/20 text-blue border border-blue/30'
                                  : winner === opponentClub
                                  ? 'bg-peach/20 text-peach border border-peach/30'
                                  : 'bg-yellow/20 text-yellow border border-yellow/30'
                              }`}
                            >
                              {winner === 'Draw' ? 'Draw' : `${winner} win`}
                            </span>
                          )}
                        </div>
                      </div>
                    );
                  })}
                </div>

                <div className="pt-2 border-t border-surface1">
                  <H2HPagination />
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

export default function ClubsPage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-text tracking-tight">Club Lab & Head-to-Head</h1>
        <p className="text-sm text-subtext0 mt-1">
          Deep-dive club performance profiling, historical season trajectories, and direct head-to-head comparison.
        </p>
      </div>

      <Suspense fallback={<LoadingSkeleton lines={10} />}>
        <ClubLabContent />
      </Suspense>
    </div>
  );
}
