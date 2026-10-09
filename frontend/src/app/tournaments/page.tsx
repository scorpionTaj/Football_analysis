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
import { Trophy, Users, Goal, Calendar, Download, Search } from 'lucide-react';
import { FootballBadge, CompetitionBadge, PlayerAvatar } from '@/lib/media-utils';
import { fuzzyMatch } from '@/lib/fuzzy';
import { Card } from '@heroui/react';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  CartesianGrid,
} from 'recharts';

const calendarYearTournaments = new Set(['WC', 'CWC', 'EURO', 'COPA', 'AFCON', 'ASIAN']);

function TournamentsContent() {
  const filters = useFilterParams();
  const { data: catalog } = useQuery({ queryKey: queryKeys.catalog, queryFn: () => api.catalog() });
  const tournamentConfigs = useMemo(() => (catalog?.competitions || [])
    .filter((competition) => competition.kind === 'tournament' && competition.seasons.length > 0)
    .map((competition) => ({
      ...competition,
      years: [...competition.seasons].sort((a, b) => b.season - a.season).map((season) => season.season),
      defaultYear: Math.max(...competition.seasons.map((season) => season.season)),
    })), [catalog?.competitions]);
  const fallbackConfig = { code: 'UCL', name: 'UEFA Champions League', group: 'Continental clubs', years: [] as number[], defaultYear: 0 };
  const currentTournamentConfig = tournamentConfigs.find((competition) => competition.code === filters.competition)
    || tournamentConfigs.find((competition) => competition.code === 'UCL')
    || tournamentConfigs[0]
    || fallbackConfig;
  const selectedTournament = currentTournamentConfig.code;
  const selectedYear = filters.season || currentTournamentConfig.defaultYear;
  const groupedTournaments = useMemo(() => tournamentConfigs.reduce((groups, competition) => {
    groups.set(competition.group, [...(groups.get(competition.group) || []), competition]);
    return groups;
  }, new Map<string, typeof tournamentConfigs>()), [tournamentConfigs]);

  const [activeTab, setActiveTab] = useState<'matches' | 'scorers' | 'performance' | 'stages'>('matches');
  const [matchSearch, setMatchSearch] = useState('');
  const [stageFilter, setStageFilter] = useState<string>('all');
  const [teamFilter, setTeamFilter] = useState<string>('all');

  const { data, isLoading, error, refetch } = useQuery({
    queryKey: queryKeys.tournament(selectedTournament, selectedYear),
    queryFn: () => api.tournament(selectedTournament, selectedYear),
    enabled: selectedYear > 0,  // wait for the catalog instead of guessing an edition
  });

  const matches = useMemo(() => data?.matches || [], [data?.matches]);
  const scorers = useMemo(() => data?.scorers || [], [data?.scorers]);
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
        if (!fuzzyMatch(matchSearch, [m.home?.name, m.away?.name, m.stage, m.venue])) {
          return false;
        }
      }
      return true;
    });
  }, [matches, stageFilter, teamFilter, matchSearch]);

  // Metrics calculation
  const totalGoals = useMemo(() => {
    return filteredMatches.reduce((acc, m) => acc + (m.home_goals || 0) + (m.away_goals || 0), 0);
  }, [filteredMatches]);

  const avgGoals = filteredMatches.length > 0 ? (totalGoals / filteredMatches.length).toFixed(2) : '0';
  const filteredTeamCount = new Set(filteredMatches.flatMap((match) => [match.home.team_id, match.away.team_id])).size;

  // Stage scoring chart data
  const stageChartData = useMemo(() => {
    const stageMap = new Map<string, { matches: number; goals: number }>();
    for (const m of filteredMatches) {
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
  }, [filteredMatches]);

  // Scorers ranking calculation
  const topScorers = useMemo(() => {
    const scorerMap = new Map<string, { player: string; team: string; goals: number; penalties: number }>();
    const selectedDates = new Set(filteredMatches.map((match) => match.match_date));
    for (const g of scorers) {
      if (g.own_goal) continue;
      if ((stageFilter !== 'all' || teamFilter !== 'all') && !selectedDates.has(g.match_date)) continue;
      if (teamFilter !== 'all' && g.team.team_id !== teamFilter) continue;
      const key = `${g.player}_${g.team.name}`;
      const existing = scorerMap.get(key) || { player: g.player, team: g.team.name, goals: 0, penalties: 0 };
      existing.goals += 1;
      if (g.penalty) existing.penalties += 1;
      scorerMap.set(key, existing);
    }
    return Array.from(scorerMap.values()).sort((a, b) => b.goals - a.goals || a.player.localeCompare(b.player));
  }, [scorers, filteredMatches, stageFilter, teamFilter]);

  const teamPerformance = useMemo(() => {
    const rows = new Map<string, { id: string; name: string; badge: string | null | undefined; played: number; wins: number; draws: number; losses: number; goalsFor: number; goalsAgainst: number; points: number; form: string[] }>();
    const ensure = (team: typeof matches[number]['home']) => {
      if (!rows.has(team.team_id)) rows.set(team.team_id, { id: team.team_id, name: team.name, badge: team.badge_url, played: 0, wins: 0, draws: 0, losses: 0, goalsFor: 0, goalsAgainst: 0, points: 0, form: [] });
      return rows.get(team.team_id)!;
    };
    for (const match of [...filteredMatches].sort((a, b) => a.match_date.localeCompare(b.match_date))) {
      if (match.home_goals == null || match.away_goals == null) continue;
      const home = ensure(match.home);
      const away = ensure(match.away);
      home.played += 1; away.played += 1;
      home.goalsFor += match.home_goals; home.goalsAgainst += match.away_goals;
      away.goalsFor += match.away_goals; away.goalsAgainst += match.home_goals;
      if (match.home_goals > match.away_goals) {
        home.wins += 1; home.points += 3; home.form.push('W'); away.losses += 1; away.form.push('L');
      } else if (match.home_goals < match.away_goals) {
        away.wins += 1; away.points += 3; away.form.push('W'); home.losses += 1; home.form.push('L');
      } else {
        home.draws += 1; away.draws += 1; home.points += 1; away.points += 1; home.form.push('D'); away.form.push('D');
      }
    }
    return Array.from(rows.values()).sort((a, b) => b.points - a.points || (b.goalsFor - b.goalsAgainst) - (a.goalsFor - a.goalsAgainst) || b.goalsFor - a.goalsFor);
  }, [filteredMatches]);

  // CSV export handler
  const exportCsv = () => {
    const headers = ['Date', 'Stage', 'Home Team', 'Score', 'Away Team', 'Penalties', 'Venue'];
    const rows = filteredMatches.map((m) => [
      m.match_date,
      m.stage || '',
      m.home.name,
      `${m.home_goals ?? ''} - ${m.away_goals ?? ''}`,
      m.away.name,
      m.home_penalties !== null && m.away_penalties !== null ? `${m.home_penalties}-${m.away_penalties}` : '',
      m.venue || '',
    ]);
    const csvContent = toCsv(headers, rows);
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
    paginationControls: MatchesPagination,
  } = usePagination(filteredMatches, 10);

  const {
    paginatedItems: paginatedScorers,
    paginationControls: ScorersPagination,
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
        <div className="flex min-w-0 items-center gap-3">
          <CompetitionBadge code={currentTournamentConfig.code} name={currentTournamentConfig.name} size={36} />
          <div className="min-w-0">
            <p className="text-[10px] font-bold uppercase tracking-[0.18em] text-blue">{currentTournamentConfig.group}</p>
            <p className="truncate text-base font-black text-text">{currentTournamentConfig.name}</p>
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-3">
          <select
            value={selectedTournament}
            onChange={(event) => {
              const competition = tournamentConfigs.find((item) => item.code === event.target.value);
              if (!competition) return;
              filters.set({ competition: competition.code, season: competition.defaultYear, team: null });
              setStageFilter('all');
              setTeamFilter('all');
            }}
            className="max-w-[18rem] rounded-lg border border-surface1 bg-surface0 px-3 py-2 text-sm text-text outline-none hover:border-surface2 focus:border-blue"
            aria-label="Tournament"
          >
            {Array.from(groupedTournaments.entries()).map(([group, competitions]) => (
              <optgroup key={group} label={group}>
                {competitions.map((competition) => <option key={competition.code} value={competition.code}>{competition.name}</option>)}
              </optgroup>
            ))}
          </select>
          {/* Year selector for current tournament */}
          <select
            value={selectedYear}
            onChange={(e) => filters.set({ season: Number(e.target.value) })}
            className="rounded-lg border border-surface1 bg-surface0 px-3 py-2 text-sm text-text outline-none hover:border-surface2 focus:border-blue cursor-pointer"
            aria-label="Tournament Edition"
          >
            {currentTournamentConfig.years.map((yr) => (
              <option key={yr} value={yr}>
                {calendarYearTournaments.has(selectedTournament)
                  ? `${yr}`
                  : `${yr}/${(yr + 1).toString().slice(2)}`}
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
          <p className="text-2xl font-bold text-text">{filteredMatches.length}</p>
        </div>

        <div className="rounded-xl bg-surface0 border border-surface1 p-4">
          <div className="flex items-center justify-between text-subtext0 mb-1">
            <span className="text-xs uppercase font-medium">Teams</span>
            <Users className="h-4 w-4 text-teal" />
          </div>
          <p className="text-2xl font-bold text-text">{filteredTeamCount}</p>
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
                  formatter={(value) => [`${value} goals/match`, 'Scoring Rate']}
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
        <div className="flex flex-wrap items-center gap-2">
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
            onClick={() => setActiveTab('performance')}
            className={`px-3.5 py-1.5 rounded-lg text-xs font-semibold transition-colors cursor-pointer ${
              activeTab === 'performance' ? 'bg-surface1 text-text' : 'text-subtext0 hover:text-text'
            }`}
          >
            Team performance ({teamPerformance.length})
          </button>
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
        <div className="flex min-w-0 flex-wrap items-center gap-2.5">
          <>
              {/* Stage filter */}
              <select
                value={stageFilter}
                onChange={(e) => setStageFilter(e.target.value)}
                className="max-w-full rounded-lg border border-surface1 bg-surface0 px-2.5 py-1.5 text-xs text-text outline-none cursor-pointer"
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
                className="max-w-full rounded-lg border border-surface1 bg-surface0 px-2.5 py-1.5 text-xs text-text outline-none cursor-pointer"
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
              {MatchesPagination}
            </>
          )}
        </div>
      )}

      {/* Tab 2: Scorers View */}
      {activeTab === 'scorers' && scorers.length > 0 && (
        <Card className="rounded-2xl border border-surface1 bg-surface0 overflow-hidden shadow-sm">
          <table className="w-full text-left text-sm">
            <thead className="border-b border-surface1 bg-mantle text-xs uppercase text-subtext0">
              <tr>
                <th className="py-3 px-4 w-16">Rank</th>
                <th className="py-3 px-4">Player</th>
                <th className="py-3 px-4">Team</th>
                <th className="py-3 px-4 text-center">Penalties</th>
                <th className="py-3 px-4 text-right">Goals</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-surface1/60">
              {paginatedScorers.map((sc, index) => {
                const rank = (scorersPage - 1) * scorersPageSize + index + 1;
                return (
                  <tr key={`${sc.player}_${sc.team}`} className="hover:bg-surface1/40 transition-colors">
                    <td className="py-3 px-4 font-mono text-xs font-bold text-subtext0">#{rank}</td>
                    <td className="py-3 px-4">
                      <div className="flex items-center gap-3">
                        <PlayerAvatar name={sc.player} size={36} ring={false} />
                        <span className="font-bold text-text">{sc.player}</span>
                      </div>
                    </td>
                    <td className="py-3 px-4 text-subtext1 font-medium">{sc.team}</td>
                    <td className="py-3 px-4 text-center text-xs text-subtext0 font-mono">
                      {sc.penalties ? `${sc.penalties}` : '—'}
                    </td>
                    <td className="py-3 px-4 text-right">
                      <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-bold bg-blue/15 text-blue font-mono">
                        {sc.goals} {sc.goals === 1 ? 'goal' : 'goals'}
                      </span>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
          <div className="p-3 bg-mantle border-t border-surface1">
            {ScorersPagination}
          </div>
        </Card>
      )}

      {activeTab === 'performance' && (
        <Card className="overflow-hidden rounded-2xl border border-surface1 bg-surface0 shadow-sm">
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="border-b border-surface1 bg-mantle uppercase text-subtext0"><tr><th className="px-4 py-3">Rank</th><th className="px-4 py-3">Team</th><th className="px-3 py-3 text-center">P</th><th className="px-3 py-3 text-center">W</th><th className="px-3 py-3 text-center">D</th><th className="px-3 py-3 text-center">L</th><th className="px-3 py-3 text-center">GF</th><th className="px-3 py-3 text-center">GA</th><th className="px-3 py-3 text-center">GD</th><th className="px-3 py-3 text-center">Form</th></tr></thead>
              <tbody className="divide-y divide-surface1">
                {teamPerformance.slice(0, 20).map((row, index) => <tr key={row.id}><td className="px-4 py-3 font-mono">{index + 1}</td><td className="px-4 py-3"><span className="flex items-center gap-2 font-semibold text-text"><FootballBadge name={row.name} url={row.badge} size={22} />{row.name}</span></td><td className="px-3 py-3 text-center">{row.played}</td><td className="px-3 py-3 text-center text-green">{row.wins}</td><td className="px-3 py-3 text-center text-yellow">{row.draws}</td><td className="px-3 py-3 text-center text-red">{row.losses}</td><td className="px-3 py-3 text-center">{row.goalsFor}</td><td className="px-3 py-3 text-center">{row.goalsAgainst}</td><td className="px-3 py-3 text-center font-mono">{row.goalsFor - row.goalsAgainst > 0 ? '+' : ''}{row.goalsFor - row.goalsAgainst}</td><td className="px-3 py-3 text-center font-mono">{row.form.slice(-5).join(' ')}</td></tr>)}
              </tbody>
            </table>
          </div>
          <p className="border-t border-surface1 p-3 text-xs text-subtext0">Performance ranking describes the selected tournament matches; it is not an official group table.</p>
        </Card>
      )}

      {/* Tab 3: Stages Summary View */}
      {activeTab === 'stages' && (
        <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-4">
          {stages.map((st) => (
            <Card key={st.stage} className="p-5 rounded-2xl bg-surface0 border border-surface1 shadow-sm hover:border-blue/50 transition-all">
              <div className="flex items-start justify-between">
                <div>
                  <p className="text-base font-bold text-text">{st.stage}</p>
                  <p className="text-xs text-subtext0 mt-1">{st.match_count} matches completed</p>
                </div>
                <span className="text-xs px-2 py-0.5 rounded-full bg-surface1 text-blue font-bold">
                  Stage
                </span>
              </div>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}

export default function TournamentsPage() {
  return (
    <div className="space-y-6">
      <PageHeader icon={Trophy} eyebrow="Knockout and international" title="Major Tournaments" description="Explore domestic cups, continental club competitions and international tournaments with stages, scorelines and scorer events." />

      <Suspense fallback={<LoadingSkeleton lines={8} />}>
        <TournamentsContent />
      </Suspense>
    </div>
  );
}
