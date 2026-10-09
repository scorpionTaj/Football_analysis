'use client';

import { Card, Button } from '@heroui/react';
import { Suspense, useCallback, useMemo, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { api } from '@/lib/api/client';
import { toCsv } from '@/lib/csv';
import { queryKeys } from '@/lib/api/query-keys';
import { useFilterParams } from '@/lib/hooks/use-filter-params';
import type { Match } from '@/lib/api/types';
import { SourceBadge } from '@/components/ui/source-badge';
import { LoadingSkeleton, ErrorMessage, EmptyState } from '@/components/ui/loading';
import { PageHeader } from '@/components/ui/page-header';
import { Shield, TrendingUp, Calendar, Trophy, Download, Swords, BarChart2 } from 'lucide-react';
import { usePagination } from '@/components/ui/pagination';
import { FootballBadge } from '@/lib/media-utils';
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

function ClubLabContent() {
  const filters = useFilterParams();
  const selectedClub = filters.team || 'Arsenal';
  const [activeTab, setActiveTab] = useState<'profile' | 'h2h'>('profile');
  const [opponentClub, setOpponentClub] = useState<string>('Chelsea');
  const [formWindow, setFormWindow] = useState(5);

  // Fetch all teams to populate the club selector
  const { data: teamData } = useQuery({
    queryKey: queryKeys.teams(),
    queryFn: () => api.teams(),
  });

  const allTeams = useMemo(() => {
    const map = new Map<string, NonNullable<typeof teamData>['teams'][number]>();
    for (const t of teamData?.teams || []) {
      const key = t.team_id || t.name;
      const existing = map.get(key);
      if (
        !existing
        || t.played > existing.played
        || (t.played === existing.played && !existing.badge_url && !!t.badge_url)
      ) {
        map.set(key, t);
      }
    }
    return Array.from(map.values()).sort((a, b) => a.name.localeCompare(b.name));
  }, [teamData]);
  const selectedTeam = allTeams.find((team) => team.name === selectedClub);
  const opponentTeam = allTeams.find((team) => team.name === opponentClub);
  const selectedTeamId = selectedTeam?.team_id;
  // Until the team list resolves the id, fall back to the name so home/away are not all read as away.
  const isClubHome = useCallback(
    (match: Match) => (selectedTeamId ? match.home.team_id === selectedTeamId : match.home.name === selectedClub),
    [selectedTeamId, selectedClub],
  );

  // Request analysis for the selected club across all seasons
  const requestBody = useMemo(() => ({
    competitions: [],
    seasons: [],
    teams: [selectedClub],
    venue: null,
    form_window: formWindow,
  }), [selectedClub, formWindow]);

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
  const { data: matchData, isLoading: isMatchesLoading, error: matchesError, refetch: refetchMatches } = useQuery({
    queryKey: queryKeys.matches({ team: selectedClub, limit: 100 }),
    queryFn: () => api.matches({ team: selectedClub, limit: 100 }),
    enabled: !!selectedClub,
  });

  // Direct filtering spans leagues and cups without losing older meetings to
  // either club's general recent-match pagination.
  const { data: h2hData, isLoading: isH2HLoading, error: h2hError, refetch: refetchH2H } = useQuery({
    queryKey: queryKeys.matches({ team: selectedClub, opponent: opponentClub, limit: 200 }),
    queryFn: () => api.matches({ team: selectedClub, opponent: opponentClub, limit: 200 }),
    enabled: activeTab === 'h2h' && !!selectedClub && !!opponentClub,
  });

  const seasonsList = useMemo(() => {
    return [...(analysis?.rankings || [])].sort((a, b) => a.season - b.season);
  }, [analysis]);

  const benchmarkRequest = useMemo(() => ({
    competitions: Array.from(new Set(seasonsList.map((row) => row.competition))),
    seasons: Array.from(new Set(seasonsList.map((row) => row.season))),
    teams: [],
    venue: null,
    form_window: formWindow,
  }), [seasonsList, formWindow]);

  const { data: benchmark } = useQuery({
    queryKey: queryKeys.analysis(benchmarkRequest),
    queryFn: () => api.analysis(benchmarkRequest),
    enabled: benchmarkRequest.competitions.length > 0,
  });

  // Paginated season history table (10 per page)
  const { paginatedItems: paginatedSeasons, paginationControls: SeasonsPagination } = usePagination(seasonsList, 10);

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

  const matches = useMemo(() => matchData?.matches || [], [matchData?.matches]);
  const rollingForm = useMemo(() => {
    const ordered = [...matches].filter((match) => match.home_goals != null && match.away_goals != null).sort((a, b) => a.match_date.localeCompare(b.match_date));
    const points: number[] = ordered.map((match) => {
      const isHome = isClubHome(match);
      const goalsFor = isHome ? match.home_goals! : match.away_goals!;
      const goalsAgainst = isHome ? match.away_goals! : match.home_goals!;
      return goalsFor > goalsAgainst ? 3 : goalsFor === goalsAgainst ? 1 : 0;
    });
    return ordered.map((match, index) => {
      const window = points.slice(Math.max(0, index - formWindow + 1), index + 1);
      return { date: match.match_date, PPG: Number((window.reduce((sum, value) => sum + value, 0) / window.length).toFixed(2)) };
    });
  }, [matches, isClubHome, formWindow]);

  const percentileProfile = useMemo(() => {
    const rows = benchmark?.rankings || [];
    const own = rows.filter((row) => row.team.name === selectedClub);
    const metrics = [
      ['Scoring', 'goals_per_game'], ['Points', 'points_per_game'],
      ['Win rate', 'win_rate'], ['Clean sheets', 'clean_sheet_rate'],
    ] as const;
    return metrics.map(([label, key]) => {
      const ownValue = own.length ? own.reduce((sum, row) => sum + row[key], 0) / own.length : 0;
      const values = rows.map((row) => row[key]);
      const percentile = values.length ? 100 * values.filter((value) => value <= ownValue).length / values.length : 0;
      return { label, percentile: Number(percentile.toFixed(0)) };
    });
  }, [benchmark?.rankings, selectedClub]);
  // Paginated club recent fixtures (10 per page)
  const { paginatedItems: paginatedMatches, paginationControls: MatchesPagination } = usePagination(matches, 10);

  // Head-to-Head matches calculation
  const h2hMatches = useMemo(() => {
    // The API has already resolved provider aliases (for example Arsenal and
    // Arsenal FC), so keep every direct result instead of re-filtering on the
    // presentation label.
    const combined = h2hData?.matches || [];
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
  }, [h2hData?.matches]);

  // Paginated Head-to-Head encounters (10 per page)
  const { paginatedItems: paginatedH2HMatches, paginationControls: H2HPagination } = usePagination(h2hMatches, 10);

  const h2hStats = useMemo(() => {
    let clubAWins = 0;
    let clubBWins = 0;
    let draws = 0;
    let clubAGoals = 0;
    let clubBGoals = 0;

    for (const m of h2hMatches) {
      if (m.home_goals === null || m.away_goals === null) continue;
      const isHomeA = isClubHome(m);
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
  }, [h2hMatches, isClubHome]);

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
    const csv = toCsv(headers, rows);
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
      <Card className="p-4 rounded-xl bg-surface0 border border-surface1 shadow-sm">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div className="flex flex-wrap items-center gap-3">
            <div className="p-2.5 rounded-lg bg-blue/10 text-blue">
              <FootballBadge name={selectedClub} url={selectedTeam?.badge_url} size={28} />
            </div>
            <div>
              <label className="text-xs font-medium text-subtext0 block">Primary Club</label>
              <select
                aria-label="Primary club"
                value={selectedClub}
                onChange={(e) => filters.set({ team: e.target.value })}
                className="mt-0.5 rounded-lg border border-surface1 bg-mantle px-3 py-1.5 text-sm font-semibold text-text outline-none cursor-pointer hover:border-surface2 focus:border-blue"
              >
                {allTeams.map((team) => (
                  <option key={`${team.team_id || 'team'}-${team.name}`} value={team.name}>{team.name}</option>
                ))}
              </select>
            </div>

            {activeTab === 'h2h' && (
              <>
                <div className="text-overlay0 font-bold px-1 text-sm">VS</div>
                <div>
                  <label className="text-xs font-medium text-subtext0 block">Opponent Club</label>
                  <select
                    aria-label="Opponent club"
                    value={opponentClub}
                    onChange={(e) => setOpponentClub(e.target.value)}
                    className="mt-0.5 rounded-lg border border-surface1 bg-mantle px-3 py-1.5 text-sm font-semibold text-text outline-none cursor-pointer hover:border-surface2 focus:border-blue"
                  >
                    {allTeams.map((team) => (
                      <option key={`${team.team_id || 'team'}-${team.name}`} value={team.name}>{team.name}</option>
                    ))}
                  </select>
                </div>
              </>
            )}
            <div>
              <label className="text-xs font-medium text-subtext0 block">Recent form</label>
              <select aria-label="Recent form window" value={formWindow} onChange={(event) => setFormWindow(Number(event.target.value))} className="mt-0.5 rounded-lg border border-surface1 bg-mantle px-3 py-1.5 text-sm font-semibold text-text outline-none">
                {[3, 5, 8, 10].map((value) => <option key={value} value={value}>Last {value}</option>)}
              </select>
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            {/* Tab switcher */}
            <div className="flex items-center bg-mantle rounded-lg p-1 border border-surface1">
              <Button
                size="sm"
                variant={activeTab === 'profile' ? 'primary' : 'ghost'}
                onPress={() => setActiveTab('profile')}
                className="flex items-center gap-1.5 text-xs font-semibold h-8 cursor-pointer"
              >
                <BarChart2 className="h-3.5 w-3.5" />
                <span>Club Profile</span>
              </Button>
              <Button
                size="sm"
                variant={activeTab === 'h2h' ? 'primary' : 'ghost'}
                onPress={() => setActiveTab('h2h')}
                className="flex items-center gap-1.5 text-xs font-semibold h-8 cursor-pointer"
              >
                <Swords className="h-3.5 w-3.5" />
                <span>Head-to-Head</span>
              </Button>
            </div>

            {analysis?.source && <SourceBadge meta={analysis.source} />}
            <Button
              size="sm"
              variant="outline"
              onPress={exportCsv}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium cursor-pointer"
            >
              <Download className="h-3.5 w-3.5 text-blue" />
              <span>Export</span>
            </Button>
          </div>
        </div>
      </Card>

      {activeTab === 'profile' ? (
        <>
          {/* Club Overview KPI Grid */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
            <Card className="rounded-xl bg-surface0 border border-surface1 p-4 shadow-sm">
              <p className="text-xs text-subtext0 uppercase font-medium">Matches (All Seasons)</p>
              <p className="text-2xl font-bold text-text mt-1">{totals.played}</p>
            </Card>
            <Card className="rounded-xl bg-surface0 border border-surface1 p-4 shadow-sm">
              <p className="text-xs text-subtext0 uppercase font-medium">Win Rate</p>
              <p className="text-2xl font-bold text-green mt-1">{totals.winRate}%</p>
            </Card>
            <Card className="rounded-xl bg-surface0 border border-surface1 p-4 shadow-sm">
              <p className="text-xs text-subtext0 uppercase font-medium">Total Points</p>
              <p className="text-2xl font-bold text-blue mt-1">{totals.points}</p>
            </Card>
            <Card className="rounded-xl bg-surface0 border border-surface1 p-4 shadow-sm">
              <p className="text-xs text-subtext0 uppercase font-medium">Overall PPG</p>
              <p className="text-2xl font-bold text-peach mt-1">{totals.ppg}</p>
            </Card>
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

          <div className="grid gap-4 lg:grid-cols-[1.4fr_1fr]">
            <div className="rounded-xl border border-surface1 bg-surface0 p-5">
              <h3 className="mb-4 font-semibold text-text">Rolling {formWindow}-match form</h3>
              <div className="h-64">
                <ResponsiveContainer width="100%" height="100%"><LineChart data={rollingForm} margin={{ top: 8, right: 12, left: -20, bottom: 0 }}><CartesianGrid strokeDasharray="3 3" stroke="#313244" /><XAxis dataKey="date" stroke="#7f849c" fontSize={10} /><YAxis domain={[0, 3]} stroke="#7f849c" fontSize={11} /><Tooltip contentStyle={{ backgroundColor: '#181825', borderColor: '#45475a', borderRadius: 8 }} /><Line type="monotone" dataKey="PPG" stroke="#94e2d5" strokeWidth={2.5} dot={false} /></LineChart></ResponsiveContainer>
              </div>
            </div>
            <div className="rounded-xl border border-surface1 bg-surface0 p-5">
              <h3 className="mb-4 font-semibold text-text">Selected-competition percentile profile</h3>
              <div className="space-y-4">{percentileProfile.map((row) => <div key={row.label}><div className="mb-1 flex justify-between text-xs"><span className="text-subtext0">{row.label}</span><span className="font-mono font-bold text-blue">{row.percentile}%</span></div><div className="h-2 overflow-hidden rounded-full bg-mantle"><div className="h-full rounded-full bg-blue" style={{ width: `${row.percentile}%` }} /></div></div>)}</div>
            </div>
          </div>

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
              {SeasonsPagination}
            </div>
          </div>

          {/* Recent Match Log for the Club (Paginated: 10 per page) */}
          <div className="rounded-xl border border-surface1 bg-surface0 p-5 space-y-4">
            <h3 className="text-base font-semibold text-text flex items-center gap-2">
              <Calendar className="h-4 w-4 text-teal" /> Recent Club Fixtures
            </h3>

            {isMatchesLoading ? (
              <LoadingSkeleton lines={4} />
            ) : matchesError ? (
              <ErrorMessage title="Fixtures unavailable" detail={matchesError.message} retry={() => refetchMatches()} />
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
                  {MatchesPagination}
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
                <div className="flex h-16 w-16 items-center justify-center rounded-2xl border border-blue/20 bg-blue/10">
                  <FootballBadge name={selectedClub} url={selectedTeam?.badge_url} size={48} />
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
                <div className="flex h-16 w-16 items-center justify-center rounded-2xl border border-peach/20 bg-peach/10">
                  <FootballBadge name={opponentClub} url={opponentTeam?.badge_url} size={48} />
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

            {isH2HLoading ? (
              <LoadingSkeleton lines={4} />
            ) : h2hError ? (
              <ErrorMessage title="Head-to-head unavailable" detail={h2hError.message} retry={() => refetchH2H()} />
            ) : h2hMatches.length === 0 ? (
              <EmptyState
                icon="⚽"
                message={`No direct matches found between ${selectedClub} and ${opponentClub} in covered fixtures.`}
                suggestion="Select any two covered clubs to search direct meetings across leagues and cups."
              />
            ) : (
              <div className="space-y-3">
                <div className="space-y-2">
                  {paginatedH2HMatches.map((m, idx) => {
                    const isHomeA = isClubHome(m);
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
                          <span className="flex items-center gap-1.5 text-subtext0">
                            <FootballBadge name={m.home.name} url={m.home.badge_url} size={20} />
                            {m.home.name} (H) vs {m.away.name} (A)
                            <FootballBadge name={m.away.name} url={m.away.badge_url} size={20} />
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
                  {H2HPagination}
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
      <PageHeader icon={Shield} eyebrow="Club intelligence" title="Club Lab & Head-to-Head" description="Profile long-term performance, inspect recent results and compare two clubs across leagues and cups." />

      <Suspense fallback={<LoadingSkeleton lines={10} />}>
        <ClubLabContent />
      </Suspense>
    </div>
  );
}
