'use client';

import { Suspense, useMemo, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { api } from '@/lib/api/client';
import { queryKeys } from '@/lib/api/query-keys';
import { useFilterParams } from '@/lib/hooks/use-filter-params';
import { SourceBadge } from '@/components/ui/source-badge';
import { LoadingSkeleton, ErrorMessage, EmptyState } from '@/components/ui/loading';
import { usePagination } from '@/components/ui/pagination';
import type { TournamentMatch, TournamentGoal } from '@/lib/api/types';
import { Trophy, Users, Goal, Calendar, Download, Search, ShieldCheck } from 'lucide-react';
import { FootballBadge, CompetitionBadge } from '@/lib/media-utils';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  CartesianGrid,
} from 'recharts';

const TOURNAMENT_CONFIGS = [
  {
    code: 'UCL',
    name: 'UEFA Champions League',
    icon: '🏆',
    defaultYear: 2025,
    years: [2025, 2024, 2023, 2022, 2021],
  },
  {
    code: 'WC',
    name: 'FIFA World Cup',
    icon: '🌍',
    defaultYear: 2026,
    years: [2026, 2022, 2018],
  },
];

function TournamentsContent() {
  const filters = useFilterParams();
  const selectedTournament = filters.competition === 'WC' ? 'WC' : 'UCL';
  const selectedYear = filters.season || (selectedTournament === 'WC' ? 2022 : 2024);

  const [activeTab, setActiveTab] = useState<'matches' | 'scorers' | 'stages'>('matches');
  const [matchSearch, setMatchSearch] = useState('');
  const [stageFilter, setStageFilter] = useState<string>('all');
  const [teamFilter, setTeamFilter] = useState<string>('all');

  const { data, isLoading, error, refetch } = useQuery({
    queryKey: queryKeys.tournament(selectedTournament, selectedYear),
    queryFn: () => api.tournament(selectedTournament, selectedYear),
  });

  const matches = data?.matches || [];
  const scorers = data?.scorers || [];
  const stages = data?.stages || [];

  // Extract unique stages and teams for local filtering
  const availableStages = useMemo(() => {
    return Array.from(new Set(matches.map((m) => m.stage).filter(Boolean))) as string[];
  }, [matches]);

  const availableTeams = useMemo(() => {
    const teams = new Map<string, string>();
    for (const m of matches) {
      if (m.home?.name) teams.set(m.home.team_id, m.home.name);
      if (m.away?.name) teams.set(m.away.team_id, m.away.name);
    }
    return Array.from(teams.entries()).sort((a, b) => a[1].localeCompare(b[1]));
  }, [matches]);

  // Filtered matches
  const filteredMatches = useMemo(() => {
    return matches.filter((m) => {
      if (stageFilter !== 'all' && m.stage !== stageFilter) return false;
      if (teamFilter !== 'all' && m.home.team_id !== teamFilter && m.away.team_id !== teamFilter) {
        return false;
      }
      if (matchSearch) {
        const query = matchSearch.toLowerCase();
        const homeName = m.home?.name?.toLowerCase() || '';
        const awayName = m.away?.name?.toLowerCase() || '';
        const stageName = m.stage?.toLowerCase() || '';
        const venueName = m.venue?.toLowerCase() || '';
        if (!homeName.includes(query) && !awayName.includes(query) && !stageName.includes(query) && !venueName.includes(query)) {
          return false;
        }
      }
      return true;
    });
  }, [matches, stageFilter, teamFilter, matchSearch]);

  // Metrics calculation
  const totalGoals = useMemo(() => {
    return matches.reduce((acc, m) => acc + (m.home_goals || 0) + (m.away_goals || 0), 0);
  }, [matches]);

  const avgGoals = matches.length > 0 ? (totalGoals / matches.length).toFixed(2) : '0';

  // Stage scoring chart data
  const stageChartData = useMemo(() => {
    const stageMap = new Map<string, { matches: number; goals: number }>();
    for (const m of matches) {
      const stage = m.stage || 'Unknown';
      const existing = stageMap.get(stage) || { matches: 0, goals: 0 };
      existing.matches += 1;
      existing.goals += (m.home_goals || 0) + (m.away_goals || 0);
      stageMap.set(stage, existing);
    }
    return Array.from(stageMap.entries()).map(([stage, stats]) => ({
      stage: stage.length > 18 ? stage.slice(0, 16) + '…' : stage,
      fullStage: stage,
      goalsPerMatch: Number((stats.goals / stats.matches).toFixed(2)),
      totalGoals: stats.goals,
      matches: stats.matches,
    }));
  }, [matches]);

  // Scorers ranking calculation
  const topScorers = useMemo(() => {
    const scorerMap = new Map<string, { player: string; team: string; goals: number; penalties: number }>();
    for (const g of scorers) {
      if (g.own_goal) continue;
      const key = `${g.player}_${g.team.name}`;
      const existing = scorerMap.get(key) || { player: g.player, team: g.team.name, goals: 0, penalties: 0 };
      existing.goals += 1;
      if (g.penalty) existing.penalties += 1;
      scorerMap.set(key, existing);
    }
    return Array.from(scorerMap.values()).sort((a, b) => b.goals - a.goals || a.player.localeCompare(b.player));
  }, [scorers]);

  // CSV export handler
  const exportCsv = () => {
    const headers = ['Date', 'Stage', 'Home Team', 'Score', 'Away Team', 'Penalties', 'Venue'];
    const rows = filteredMatches.map((m) => [
      m.match_date,
      `"${m.stage || ''}"`,
      `"${m.home.name}"`,
      `${m.home_goals ?? ''} - ${m.away_goals ?? ''}`,
      `"${m.away.name}"`,
      m.home_penalties !== null && m.away_penalties !== null ? `${m.home_penalties}-${m.away_penalties}` : '',
      `"${m.venue || ''}"`,
    ]);
    const csvContent = [headers.join(','), ...rows.map((r) => r.join(','))].join('\n');
    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.setAttribute('href', url);
    link.setAttribute('download', `${selectedTournament}_${selectedYear}_matches.csv`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  const {
    paginatedItems: paginatedMatches,
    PaginationComponent: MatchesPagination,
  } = usePagination(filteredMatches, 10);

  const {
    paginatedItems: paginatedScorers,
    PaginationComponent: ScorersPagination,
    currentPage: scorersPage,
    pageSize: scorersPageSize,
  } = usePagination(topScorers, 10);

  if (isLoading) return <LoadingSkeleton lines={8} />;
  if (error) {
    return <ErrorMessage title="Failed to load tournament" detail={error.message} retry={() => refetch()} />;
  }

  return (
    <div className="space-y-6">
      {/* Tournament Selector Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-surface0 pb-5">
        <div className="flex items-center gap-3">
          {TOURNAMENT_CONFIGS.map((t) => {
            const active = selectedTournament === t.code;
            return (
              <button
                key={t.code}
                onClick={() => {
                  filters.set({ competition: t.code, season: t.defaultYear, team: null });
                  setStageFilter('all');
                  setTeamFilter('all');
                }}
                className={`flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-semibold transition-all cursor-pointer ${
                  active
                    ? 'bg-blue text-crust shadow-lg shadow-blue/20'
                    : 'bg-surface0 text-subtext1 hover:bg-surface1 hover:text-text'
                }`}
              >
                <CompetitionBadge code={t.code} name={t.name} size={20} />
                <span>{t.name}</span>
              </button>
            );
          })}
        </div>

        <div className="flex items-center gap-3">
          {/* Year selector for current tournament */}
          <select
            value={selectedYear}
            onChange={(e) => filters.set({ season: Number(e.target.value) })}
            className="rounded-lg border border-surface1 bg-surface0 px-3 py-2 text-sm text-text outline-none hover:border-surface2 focus:border-blue cursor-pointer"
            aria-label="Tournament Edition"
          >
            {(TOURNAMENT_CONFIGS.find((t) => t.code === selectedTournament)?.years || [selectedYear]).map((yr) => (
              <option key={yr} value={yr}>
                {selectedTournament === 'WC' ? `${yr}` : `${yr}/${(yr + 1).toString().slice(2)}`}
              </option>
            ))}
          </select>
          {data?.source && <SourceBadge meta={data.source} />}
        </div>
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
        <div className="rounded-xl bg-surface0 border border-surface1 p-4">
          <div className="flex items-center justify-between text-subtext0 mb-1">
            <span className="text-xs uppercase font-medium">Matches</span>
            <Calendar className="h-4 w-4 text-blue" />
          </div>
          <p className="text-2xl font-bold text-text">{matches.length}</p>
        </div>

        <div className="rounded-xl bg-surface0 border border-surface1 p-4">
          <div className="flex items-center justify-between text-subtext0 mb-1">
            <span className="text-xs uppercase font-medium">Teams</span>
            <Users className="h-4 w-4 text-teal" />
          </div>
          <p className="text-2xl font-bold text-text">{availableTeams.length}</p>
        </div>

        <div className="rounded-xl bg-surface0 border border-surface1 p-4">
          <div className="flex items-center justify-between text-subtext0 mb-1">
            <span className="text-xs uppercase font-medium">Total Goals</span>
            <Goal className="h-4 w-4 text-peach" />
          </div>
          <p className="text-2xl font-bold text-text">{totalGoals}</p>
        </div>

        <div className="rounded-xl bg-surface0 border border-surface1 p-4">
          <div className="flex items-center justify-between text-subtext0 mb-1">
            <span className="text-xs uppercase font-medium">Goals / Match</span>
            <Trophy className="h-4 w-4 text-mauve" />
          </div>
          <p className="text-2xl font-bold text-blue">{avgGoals}</p>
        </div>
      </div>

      {/* Stage scoring chart */}
      {stageChartData.length > 0 && (
        <div className="rounded-xl bg-surface0 border border-surface1 p-5">
          <h2 className="text-base font-semibold text-text mb-4 flex items-center gap-2">
            <Trophy className="h-4 w-4 text-blue" /> Goals per Match by Stage
          </h2>
          <div className="h-64 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={stageChartData} margin={{ top: 10, right: 10, left: -20, bottom: 20 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#313244" vertical={false} />
                <XAxis dataKey="stage" stroke="#7f849c" fontSize={11} angle={-25} textAnchor="end" />
                <YAxis stroke="#7f849c" fontSize={11} />
                <Tooltip
                  contentStyle={{ backgroundColor: '#181825', borderColor: '#45475a', borderRadius: '8px', color: '#cdd6f4' }}
                  formatter={(value: any) => [`${value} goals/match`, 'Scoring Rate']}
                  labelFormatter={(lbl) => `Stage: ${lbl}`}
                />
                <Bar dataKey="goalsPerMatch" fill="#89b4fa" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}

      {/* Filter and Tab Bar */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 bg-mantle p-3 rounded-xl border border-surface0">
        <div className="flex items-center gap-2">
          <button
            onClick={() => setActiveTab('matches')}
            className={`px-3.5 py-1.5 rounded-lg text-xs font-semibold transition-colors cursor-pointer ${
              activeTab === 'matches' ? 'bg-surface1 text-text' : 'text-subtext0 hover:text-text'
            }`}
          >
            Matches ({filteredMatches.length})
          </button>
          {scorers.length > 0 && (
            <button
              onClick={() => setActiveTab('scorers')}
              className={`px-3.5 py-1.5 rounded-lg text-xs font-semibold transition-colors cursor-pointer ${
                activeTab === 'scorers' ? 'bg-surface1 text-text' : 'text-subtext0 hover:text-text'
              }`}
            >
              Top Scorers ({topScorers.length})
            </button>
          )}
          <button
            onClick={() => setActiveTab('stages')}
            className={`px-3.5 py-1.5 rounded-lg text-xs font-semibold transition-colors cursor-pointer ${
              activeTab === 'stages' ? 'bg-surface1 text-text' : 'text-subtext0 hover:text-text'
            }`}
          >
            Stages ({stages.length})
          </button>
        </div>

        {/* Local Search and Export */}
        <div className="flex items-center gap-2.5">
          {activeTab === 'matches' && (
            <>
              {/* Stage filter */}
              <select
                value={stageFilter}
                onChange={(e) => setStageFilter(e.target.value)}
                className="rounded-lg border border-surface1 bg-surface0 px-2.5 py-1.5 text-xs text-text outline-none cursor-pointer"
                aria-label="Filter stage"
              >
                <option value="all">All Stages</option>
                {availableStages.map((st) => (
                  <option key={st} value={st}>{st}</option>
                ))}
              </select>

              {/* Team filter */}
              <select
                value={teamFilter}
                onChange={(e) => setTeamFilter(e.target.value)}
                className="rounded-lg border border-surface1 bg-surface0 px-2.5 py-1.5 text-xs text-text outline-none cursor-pointer"
                aria-label="Filter team"
              >
                <option value="all">All Teams</option>
                {availableTeams.map(([id, name]) => (
                  <option key={id} value={id}>{name}</option>
                ))}
              </select>

              {/* Search input */}
              <div className="relative">
                <Search className="absolute left-2.5 top-2 h-3.5 w-3.5 text-overlay0" />
                <input
                  type="text"
                  placeholder="Search..."
                  value={matchSearch}
                  onChange={(e) => setMatchSearch(e.target.value)}
                  className="rounded-lg border border-surface1 bg-surface0 pl-8 pr-3 py-1.5 text-xs text-text outline-none focus:border-blue w-32 sm:w-44"
                />
              </div>

              {/* Download CSV */}
              <button
                onClick={exportCsv}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-surface0 border border-surface1 hover:border-surface2 text-xs font-medium text-text transition-colors cursor-pointer"
                title="Export matches to CSV"
              >
                <Download className="h-3.5 w-3.5 text-blue" />
                <span>Export</span>
              </button>
            </>
          )}
        </div>
      </div>

      {/* Tab 1: Matches View */}
      {activeTab === 'matches' && (
        <div className="space-y-2">
          {filteredMatches.length === 0 ? (
            <EmptyState icon="⚽" message="No matches match the selected criteria" />
          ) : (
            <>
              {paginatedMatches.map((m, idx) => (
                <div
                  key={`${m.match_date}_${m.home.team_id}_${m.away.team_id}_${idx}`}
                  className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 p-4 rounded-xl bg-surface0 border border-surface1 hover:border-surface2 transition-colors"
                >
                  {/* Match Metadata */}
                  <div className="flex items-center gap-3 text-xs text-subtext0">
                    <span className="font-mono text-overlay1">{m.match_date}</span>
                    {m.stage && (
                      <span className="rounded bg-surface1 px-2 py-0.5 text-subtext1 font-medium">
                        {m.stage}
                      </span>
                    )}
                    {m.venue && <span className="hidden md:inline text-overlay0">📍 {m.venue}</span>}
                  </div>

                  {/* Scoreline */}
                  <div className="flex items-center justify-center gap-3 sm:gap-6 flex-1 sm:px-8">
                    <div className="w-1/2 flex items-center justify-end gap-2 font-semibold text-text truncate">
                      <span className="truncate">{m.home.name}</span>
                      <FootballBadge url={m.home.badge_url} name={m.home.name} size={22} />
                    </div>
                    <div className="flex flex-col items-center justify-center min-w-[70px]">
                      <span className="rounded-md bg-mantle border border-surface1 px-3 py-1 text-sm font-bold text-blue tracking-wider">
                        {m.home_goals !== null ? m.home_goals : '-'} : {m.away_goals !== null ? m.away_goals : '-'}
                      </span>
                      {m.home_penalties !== null && m.away_penalties !== null && (
                        <span className="text-[10px] text-yellow font-medium mt-0.5">
                          ({m.home_penalties}-{m.away_penalties} pens)
                        </span>
                      )}
                    </div>
                    <div className="w-1/2 flex items-center justify-start gap-2 font-semibold text-text truncate">
                      <FootballBadge url={m.away.badge_url} name={m.away.name} size={22} />
                      <span className="truncate">{m.away.name}</span>
                    </div>
                  </div>

                  {/* Source or status */}
                  <div className="text-right text-xs text-overlay0 hidden sm:block min-w-[80px]">
                    {m.status || 'FT'}
                  </div>
                </div>
              ))}
              <MatchesPagination />
            </>
          )}
        </div>
      )}

      {/* Tab 2: Scorers View */}
      {activeTab === 'scorers' && scorers.length > 0 && (
        <div className="rounded-xl border border-surface1 bg-surface0 overflow-hidden">
          <table className="w-full text-left text-sm">
            <thead className="border-b border-surface1 bg-mantle text-xs uppercase text-subtext0">
              <tr>
                <th className="py-3 px-4">Rank</th>
                <th className="py-3 px-4">Player</th>
                <th className="py-3 px-4">Team</th>
                <th className="py-3 px-4 text-center">Penalties</th>
                <th className="py-3 px-4 text-right">Goals</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-surface1">
              {paginatedScorers.map((sc, index) => {
                const rank = (scorersPage - 1) * scorersPageSize + index + 1;
                return (
                  <tr key={`${sc.player}_${sc.team}`} className="hover:bg-surface1/50 transition-colors">
                    <td className="py-2.5 px-4 font-mono text-xs text-subtext0">#{rank}</td>
                    <td className="py-2.5 px-4 font-semibold text-text">{sc.player}</td>
                    <td className="py-2.5 px-4 text-subtext1">{sc.team}</td>
                    <td className="py-2.5 px-4 text-center text-xs text-subtext0">{sc.penalties || '-'}</td>
                    <td className="py-2.5 px-4 text-right font-bold text-blue">{sc.goals}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
          <div className="p-3 bg-mantle border-t border-surface1">
            <ScorersPagination />
          </div>
        </div>
      )}

      {/* Tab 3: Stages Summary View */}
      {activeTab === 'stages' && (
        <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-3">
          {stages.map((st) => (
            <div key={st.stage} className="p-4 rounded-xl bg-surface0 border border-surface1">
              <p className="text-sm font-semibold text-text">{st.stage}</p>
              <p className="text-xs text-subtext0 mt-1">{st.match_count} matches scheduled</p>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export default function TournamentsPage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-text tracking-tight">Champions League & World Cup</h1>
        <p className="text-sm text-subtext0 mt-1">
          CC0 OpenFootball tournament fixtures, knockout rounds, stage progression, and top scorers.
        </p>
      </div>

      <Suspense fallback={<LoadingSkeleton lines={8} />}>
        <TournamentsContent />
      </Suspense>
    </div>
  );
}
