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
import { Trophy, Download, Search } from 'lucide-react';
import { FootballBadge, CompetitionBadge, PlayerAvatar } from '@/lib/media-utils';
import { fuzzyMatch } from '@/lib/fuzzy';
import { Button } from '@heroui/react';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  CartesianGrid,
} from 'recharts';
import { axisProps, gridProps, tooltipProps } from '@/lib/chart-theme';
import { Panel } from '@/components/ui/panel';
import { Select } from '@/components/ui/select';
import { Segmented } from '@/components/ui/segmented';
import { Stat, StatGrid } from '@/components/ui/stat';
import { Chip, FormChip } from '@/components/ui/chip';
import { DataTable, TBody, THead, Td, Th } from '@/components/ui/data-table';

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

  const editionLabel = (yr: number) => calendarYearTournaments.has(selectedTournament) ? `${yr}` : `${yr}/${(yr + 1).toString().slice(2)}`;
  const tabs = [
    { value: 'matches' as const, label: `Matches (${filteredMatches.length})` },
    ...(scorers.length > 0 ? [{ value: 'scorers' as const, label: `Top scorers (${topScorers.length})` }] : []),
    { value: 'performance' as const, label: `Team performance (${teamPerformance.length})` },
    { value: 'stages' as const, label: `Stages (${stages.length})` },
  ];

  return (
    <div className="space-y-4">
      <Panel bodyClassName="flex flex-col justify-between gap-4 lg:flex-row lg:items-end">
        <div className="flex min-w-0 items-center gap-3">
          <CompetitionBadge code={currentTournamentConfig.code} name={currentTournamentConfig.name} size={36} />
          <div className="min-w-0">
            <p className="text-xs text-subtext0">{currentTournamentConfig.group}</p>
            <p className="truncate text-[16px] font-semibold text-text">{currentTournamentConfig.name}</p>
          </div>
        </div>
        <div className="flex flex-wrap items-end gap-2">
          <Select hideLabel label="Tournament" value={selectedTournament}
            onChange={(value) => {
              const competition = tournamentConfigs.find((item) => item.code === value);
              if (!competition) return;
              filters.set({ competition: competition.code, season: competition.defaultYear, team: null });
              setStageFilter('all');
              setTeamFilter('all');
            }}
            options={Array.from(groupedTournaments.entries()).flatMap(([group, competitions]) => competitions.map((competition) => ({ value: competition.code, label: competition.name, group })))}
            className="w-64" />
          <Select hideLabel label="Tournament Edition" value={String(selectedYear)} onChange={(value) => filters.set({ season: Number(value) })}
            options={currentTournamentConfig.years.map((yr) => ({ value: String(yr), label: editionLabel(yr) }))} className="w-28" />
          {data?.source && <SourceBadge meta={data.source} />}
        </div>
      </Panel>

      <StatGrid>
        <Stat label="Matches" value={filteredMatches.length} />
        <Stat label="Teams" value={filteredTeamCount} />
        <Stat label="Total goals" value={totalGoals} />
        <Stat label="Goals / match" value={avgGoals} />
      </StatGrid>

      {stageChartData.length > 0 && (
        <Panel title="Goals per match by stage">
          <div className="h-60 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={stageChartData} margin={{ top: 4, right: 8, left: -20, bottom: 20 }}>
                <CartesianGrid {...gridProps} />
                <XAxis dataKey="stage" {...axisProps} angle={-25} textAnchor="end" />
                <YAxis {...axisProps} />
                <Tooltip {...tooltipProps} formatter={(value) => [`${value} goals/match`, 'Scoring rate']} labelFormatter={(lbl) => `Stage: ${lbl}`} />
                <Bar dataKey="goalsPerMatch" fill="var(--series-1)" radius={[3, 3, 0, 0]} maxBarSize={48} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </Panel>
      )}

      <div className="flex flex-col justify-between gap-3 xl:flex-row xl:items-center">
        <Segmented label="Tournament view" value={activeTab} onChange={setActiveTab} options={tabs} />
        <div className="flex min-w-0 flex-wrap items-center gap-2">
          <Select hideLabel label="Filter stage" value={stageFilter} onChange={setStageFilter}
            options={[{ value: 'all', label: 'All stages' }, ...availableStages.map((stage) => ({ value: stage, label: stage }))]} className="w-40" />
          <Select hideLabel label="Filter team" value={teamFilter} onChange={setTeamFilter}
            options={[{ value: 'all', label: 'All teams' }, ...availableTeams.map(([id, name]) => ({ value: id, label: name }))]} className="w-44" />
          <span className="relative">
            <Search className="pointer-events-none absolute left-2.5 top-1/2 size-3.5 -translate-y-1/2 text-overlay0" aria-hidden="true" />
            <input type="text" aria-label="Search tournament matches" placeholder="Search…" value={matchSearch} onChange={(e) => setMatchSearch(e.target.value)}
              className="h-9 w-40 rounded-lg border border-surface1 bg-surface0 pl-8 pr-3 text-[13px] text-text placeholder:text-overlay0 focus:border-accent sm:w-48" />
          </span>
          <Button size="sm" variant="outline" onPress={exportCsv}>
            <Download className="size-3.5" aria-hidden="true" /> Export
          </Button>
        </div>
      </div>

      {activeTab === 'matches' && (
        filteredMatches.length === 0 ? (
          <Panel><EmptyState icon={Trophy} message="No matches match the selected criteria" /></Panel>
        ) : (
          <Panel bodyClassName="p-0">
            <ul>
              {paginatedMatches.map((m, idx) => (
                <li key={`${m.match_date}_${m.home.team_id}_${m.away.team_id}_${idx}`}
                  className="grid grid-cols-1 gap-2 border-b border-surface1 px-4 py-2.5 last:border-b-0 sm:grid-cols-[11rem_minmax(0,1fr)_5rem] sm:items-center">
                  <span className="flex min-w-0 items-center gap-2 text-xs text-subtext0">
                    <span className="tabular-nums">{m.match_date}</span>
                    {m.stage && <Chip className="truncate">{m.stage}</Chip>}
                  </span>
                  <span className="grid min-w-0 grid-cols-[minmax(0,1fr)_auto_minmax(0,1fr)] items-center gap-3 text-[13px] font-medium text-text">
                    <span className="flex min-w-0 items-center justify-end gap-2"><span className="truncate">{m.home.name}</span><FootballBadge url={m.home.badge_url} name={m.home.name} size={20} /></span>
                    <span className="flex min-w-16 flex-col items-center">
                      <span className="rounded-md bg-mantle px-2 py-0.5 text-sm font-semibold tabular-nums">
                        {m.home_goals !== null ? m.home_goals : '–'} : {m.away_goals !== null ? m.away_goals : '–'}
                      </span>
                      {m.home_penalties !== null && m.away_penalties !== null && (
                        <span className="mt-0.5 text-xs tabular-nums text-subtext0">({m.home_penalties}–{m.away_penalties} pens)</span>
                      )}
                    </span>
                    <span className="flex min-w-0 items-center gap-2"><FootballBadge url={m.away.badge_url} name={m.away.name} size={20} /><span className="truncate">{m.away.name}</span></span>
                  </span>
                  <span className="hidden text-right text-xs text-subtext0 sm:block">{m.status || 'FT'}</span>
                </li>
              ))}
            </ul>
            <div className="px-4 pb-3">{MatchesPagination}</div>
          </Panel>
        )
      )}

      {activeTab === 'scorers' && scorers.length > 0 && (
        <Panel bodyClassName="p-0">
          <DataTable minWidth={520} caption="Top scorers">
            <THead><tr><Th className="w-16">Rank</Th><Th>Player</Th><Th>Team</Th><Th align="right">Penalties</Th><Th align="right">Goals</Th></tr></THead>
            <TBody>
              {paginatedScorers.map((sc, index) => (
                <tr key={`${sc.player}_${sc.team}`}>
                  <Td className="text-subtext0">{(scorersPage - 1) * scorersPageSize + index + 1}</Td>
                  <Td><span className="flex items-center gap-2.5 font-medium"><PlayerAvatar name={sc.player} size={26} ring={false} />{sc.player}</span></Td>
                  <Td className="text-subtext1">{sc.team}</Td>
                  <Td align="right" className="text-subtext0">{sc.penalties ? sc.penalties : '—'}</Td>
                  <Td align="right" className="font-semibold">{sc.goals}</Td>
                </tr>
              ))}
            </TBody>
          </DataTable>
          <div className="px-4 pb-3">{ScorersPagination}</div>
        </Panel>
      )}

      {activeTab === 'performance' && (
        <Panel bodyClassName="p-0">
          <DataTable minWidth={680} caption="Team performance">
            <THead><tr><Th>Rank</Th><Th>Team</Th><Th align="right">P</Th><Th align="right">W</Th><Th align="right">D</Th><Th align="right">L</Th><Th align="right">GF</Th><Th align="right">GA</Th><Th align="right">GD</Th><Th align="center">Form</Th></tr></THead>
            <TBody>
              {teamPerformance.slice(0, 20).map((row, index) => {
                const gd = row.goalsFor - row.goalsAgainst;
                return (
                  <tr key={row.id}>
                    <Td className="text-subtext0">{index + 1}</Td>
                    <Td><span className="flex items-center gap-2 font-medium"><FootballBadge name={row.name} url={row.badge} size={20} />{row.name}</span></Td>
                    <Td align="right" className="text-subtext1">{row.played}</Td>
                    <Td align="right" className="text-subtext1">{row.wins}</Td>
                    <Td align="right" className="text-subtext1">{row.draws}</Td>
                    <Td align="right" className="text-subtext1">{row.losses}</Td>
                    <Td align="right" className="text-subtext1">{row.goalsFor}</Td>
                    <Td align="right" className="text-subtext1">{row.goalsAgainst}</Td>
                    <Td align="right" className={gd > 0 ? 'text-positive' : gd < 0 ? 'text-negative' : 'text-subtext0'}>{gd > 0 ? '+' : ''}{gd}</Td>
                    <Td align="center"><span className="inline-flex gap-1">{row.form.slice(-5).map((result, i) => <FormChip key={i} result={result} />)}</span></Td>
                  </tr>
                );
              })}
            </TBody>
          </DataTable>
          <p className="border-t border-surface1 px-4 py-3 text-xs text-subtext0">Performance ranking describes the selected tournament matches; it is not an official group table.</p>
        </Panel>
      )}

      {activeTab === 'stages' && (
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 md:grid-cols-3">
          {stages.map((st) => (
            <Stat key={st.stage} label={st.stage} value={st.match_count} hint="matches completed" />
          ))}
        </div>
      )}
    </div>
  );
}

export default function TournamentsPage() {
  return (
    <div className="space-y-5">
      <PageHeader icon={Trophy} eyebrow="Knockout and international" title="Major Tournaments" description="Explore domestic cups, continental club competitions and international tournaments with stages, scorelines and scorer events." />

      <Suspense fallback={<LoadingSkeleton lines={8} />}>
        <TournamentsContent />
      </Suspense>
    </div>
  );
}
