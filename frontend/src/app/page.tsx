'use client';

import React, { Suspense, useEffect, useMemo, useRef, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import Link from 'next/link';
import { api } from '@/lib/api/client';
import { queryKeys } from '@/lib/api/query-keys';
import { SourceBadge } from '@/components/ui/source-badge';
import { LoadingSkeleton, ErrorMessage } from '@/components/ui/loading';
import { FootballBadge, CompetitionBadge, PlayerAvatar } from '@/lib/media-utils';
import { fuzzySort } from '@/lib/fuzzy';
import type { Competition } from '@/lib/api/types';
import {
  Card,
  Chip,
  Button,
  Input,
} from '@heroui/react';
import {
  Trophy,
  TrendingUp,
  Activity,
  Calendar,
  Shield,
  Zap,
  ChevronRight,
  ChevronLeft,
  ExternalLink,
  Sparkles,
  ArrowRightLeft,
} from 'lucide-react';
import {
  ResponsiveContainer,
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip as RechartsTooltip,
  Legend,
  CartesianGrid,
  ScatterChart,
  Scatter,
  ZAxis,
  Cell,
} from 'recharts';

const CHART_COLORS = [
  '#89b4fa', // blue
  '#a6e3a1', // green
  '#fab387', // peach
  '#f38ba8', // red
  '#cba6f7', // mauve
  '#94e2d5', // teal
  '#f9e2af', // yellow
  '#74c7ec', // sapphire
];

const BIG_5_COMPS = [
  { code: 'all', name: 'All Big 5 Leagues' },
  { code: 'E0', name: 'Premier League' },
  { code: 'SP1', name: 'La Liga' },
  { code: 'D1', name: 'Bundesliga' },
  { code: 'I1', name: 'Serie A' },
  { code: 'F1', name: 'Ligue 1' },
];

const RECENT_TRANSFER_SEASONS = [
  { value: 'all', label: 'All available seasons' },
  { value: 2026, label: '2026/27' },
  { value: 2025, label: '2025/26' },
  { value: 2024, label: '2024/25' },
  { value: 2023, label: '2023/24' },
  { value: 2022, label: '2022/23' },
  { value: 2021, label: '2021/22' },
];

function CompetitionChoice({ comp, selected, onSelect }: { comp: Competition; selected: boolean; onSelect: () => void }) {
  return (
    <button
      type="button"
      onClick={onSelect}
      aria-pressed={selected}
      className={`flex min-h-11 min-w-0 items-center gap-2.5 rounded-xl border px-3.5 py-2 text-left text-xs font-semibold transition-colors focus-visible:outline-2 focus-visible:outline-blue ${selected
        ? 'border-blue bg-blue/15 text-blue'
        : 'border-surface1 bg-surface0 text-subtext1 hover:border-surface2 hover:text-text'}`}
    >
      <CompetitionBadge code={comp.code} name={comp.name} badge_url={comp.badge_url} size={24} />
      <span className="min-w-0 break-words">{comp.name}</span>
      {comp.kind === 'tournament' ? <Chip color="warning" variant="soft" size="sm" className="ml-auto text-[10px]">Cup</Chip> : null}
    </button>
  );
}

function OverviewContent() {
  const [selectedComp, setSelectedComp] = useState<string>('E0');
  const [selectedSeason, setSelectedSeason] = useState<number>(2026);
  const [selectedClub, setSelectedClub] = useState<string>('');
  const [chartView, setChartView] = useState<'trend' | 'matrix' | 'scatter' | 'elo'>('trend');
  const [showAllCompetitions, setShowAllCompetitions] = useState(false);
  const [competitionSearch, setCompetitionSearch] = useState('');
  const [marketVisible, setMarketVisible] = useState(false);
  const marketRef = useRef<HTMLDivElement>(null);

  // Transfer Market Filter & Pagination State
  const [transferComp, setTransferComp] = useState<string>('all');
  const [transferSeason, setTransferSeason] = useState<number | 'all'>('all');
  const [transferPage, setTransferPage] = useState<number>(1);
  const transferPageSize = 10;

  // 1. Fetch Catalog
  const { data: catalog, isLoading: isCatalogLoading, error: catalogError, refetch: refetchCatalog } = useQuery({
    queryKey: queryKeys.catalog,
    queryFn: () => api.catalog(),
  });

  useEffect(() => {
    const section = marketRef.current;
    if (!section || marketVisible) return;
    if (typeof IntersectionObserver === 'undefined') {
      const frame = window.requestAnimationFrame(() => setMarketVisible(true));
      return () => window.cancelAnimationFrame(frame);
    }
    const observer = new IntersectionObserver(([entry]) => {
      if (entry.isIntersecting) setMarketVisible(true);
    }, { rootMargin: '400px' });
    observer.observe(section);
    return () => observer.disconnect();
  }, [catalog, marketVisible]);

  // Current active competition object
  const currentComp = useMemo(() => {
    return catalog?.competitions.find((c) => c.code === selectedComp);
  }, [catalog, selectedComp]);

  // Available seasons for this competition (sorted newest first)
  const availableSeasons = useMemo(() => {
    if (!currentComp) return [2026, 2025, 2024, 2023, 2022, 2021];
    return [...currentComp.seasons.map((s) => s.season)].sort((a, b) => b - a);
  }, [currentComp]);

  // 2. Fetch Health
  const { data: health } = useQuery({
    queryKey: queryKeys.health,
    queryFn: () => api.health(),
  });

  // 3. Fetch Teams in this competition & season (to populate all real clubs)
  const { data: teamsData } = useQuery({
    queryKey: queryKeys.teams(selectedComp, selectedSeason),
    queryFn: () => api.teams(selectedComp, selectedSeason),
    enabled: Boolean(selectedComp),
  });

  // 4. Fetch Overview Spotlight & Trends
  const { data: overviewData } = useQuery({
    queryKey: queryKeys.overview({ team: selectedClub || undefined, competition: selectedComp, season: selectedSeason }),
    queryFn: () => api.overview({ team: selectedClub || undefined, competition: selectedComp, season: selectedSeason }),
  });

  // Available clubs in this competition
  const availableClubs = useMemo(() => {
    const names = new Set<string>();
    if (teamsData?.teams && teamsData.teams.length > 0) {
      for (const t of teamsData.teams) {
        if (t.name) names.add(t.name);
      }
    }
    if (overviewData?.performance_over_time) {
      for (const r of overviewData.performance_over_time) {
        if (r.competition === selectedComp && r.team?.name) {
          names.add(r.team.name);
        }
      }
    }
    return Array.from(names).sort((a, b) => a.localeCompare(b));
  }, [teamsData, overviewData, selectedComp]);

  const activeClub = selectedClub && availableClubs.includes(selectedClub)
    ? selectedClub
    : overviewData?.spotlight?.team?.name || availableClubs[0] || '';

  // Handle Competition Change
  const handleSelectComp = (code: string) => {
    setSelectedComp(code);
    setShowAllCompetitions(false);
    setCompetitionSearch('');
    setSelectedClub(''); // Reset so backend auto-picks #1 club in this league
    const comp = catalog?.competitions.find((c) => c.code === code);
    if (comp && comp.seasons.length > 0) {
      const latest = Math.max(...comp.seasons.map((s) => s.season));
      setSelectedSeason(latest);
    }
  };

  // 5. Fetch Star Players
  const { data: starPlayersData } = useQuery({
    queryKey: queryKeys.players({ sort_by: 'market_value', limit: 8 }),
    queryFn: () => api.players({ sort_by: 'market_value', limit: 8 }),
    enabled: marketVisible,
  });

  // 6. Fetch Transfer Market (Top 5 Competitions & Last 5 Seasons)
  const { data: transfersData, isLoading: isTransfersLoading } = useQuery({
    queryKey: queryKeys.transfers({
      competition: transferComp === 'all' ? undefined : transferComp,
      season: transferSeason === 'all' ? undefined : transferSeason,
      limit: 100,
    }),
    queryFn: () =>
      api.transfers({
        competition: transferComp === 'all' ? undefined : transferComp,
        season: transferSeason === 'all' ? undefined : transferSeason,
        limit: 100,
      }),
    enabled: marketVisible,
  });

  const allTransfers = useMemo(() => transfersData?.transfers || [], [transfersData?.transfers]);
  const totalTransferPages = Math.max(1, Math.ceil(allTransfers.length / transferPageSize));
  const paginatedTransfers = useMemo(() => {
    const start = (transferPage - 1) * transferPageSize;
    return allTransfers.slice(start, start + transferPageSize);
  }, [allTransfers, transferPage]);

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

  if (isCatalogLoading) return <LoadingSkeleton lines={10} />;
  if (catalogError) {
    return (
      <ErrorMessage
        title="Failed to load catalog"
        detail={catalogError.message}
        retry={() => refetchCatalog()}
      />
    );
  }
  if (!catalog) return null;

  const totalMatches = catalog.competitions
    .flatMap((c) => c.seasons)
    .reduce((sum, s) => sum + s.match_count, 0);

  const spotlight = overviewData?.spotlight;
  const nextListedMatch = spotlight?.next_match || spotlight?.next_fixture;
  const featuredCompetitions = catalog.competitions.filter((comp) =>
    BIG_5_COMPS.some((featured) => featured.code === comp.code) || comp.code === selectedComp);
  const quickCompetitions = featuredCompetitions.length ? featuredCompetitions : catalog.competitions.slice(0, 6);
  const matchingCompetitions = competitionSearch.trim()
    ? fuzzySort(competitionSearch, catalog.competitions, (comp) => `${comp.name} ${comp.code} ${comp.group}`)
    : catalog.competitions;
  const competitionGroups = [...new Set(matchingCompetitions.map((comp) => comp.group))];

  return (
    <div className="space-y-8 animate-fade-in pb-12">
      {/* 1. Header & Live Indicator */}
      <Card className="page-intro relative overflow-hidden rounded-3xl border border-surface1/70 bg-surface0/75 p-5 shadow-xl shadow-crust/10 sm:p-7">
        <div className="relative z-10 flex flex-col gap-5 md:flex-row md:items-center md:justify-between">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span className="flex h-2.5 w-2.5 relative">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-green opacity-75"></span>
              <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-green"></span>
            </span>
            <span className="text-xs font-semibold text-green">
              Matchday workspace
            </span>
          </div>
          <h1 className="text-3xl font-black tracking-[-0.04em] text-text sm:text-4xl">
            Football intelligence, from fixture to forecast
          </h1>
          <p className="text-sm text-subtext0 mt-0.5">
            Explore sourced fixtures, club form, players and model forecasts in one place.
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <div className="flex items-center gap-2 px-3 py-1.5 rounded-full bg-surface0 border border-surface1 text-xs text-subtext1 shadow-sm">
            <span className={`h-2 w-2 rounded-full ${health?.status === 'ok' ? 'bg-green' : 'bg-red'}`} />
            <span>API {health?.status ?? 'Connecting'}</span>
            <span className="text-overlay0">•</span>
            <span>{totalMatches.toLocaleString()} Matches</span>
            <span className="text-overlay0">•</span>
            <span>{catalog.competitions.length} Competitions</span>
          </div>
          {overviewData?.source && <SourceBadge meta={overviewData.source} />}
        </div>
        </div>
      </Card>

      {/* 2. Featured competitions and full catalog */}
      <div>
        <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
          <h2 className="flex items-center gap-1.5 text-sm font-bold text-text">
            <Trophy size={16} className="text-yellow" /> Choose a competition
          </h2>
          <Button size="sm" variant="outline" onPress={() => setShowAllCompetitions((open) => !open)} aria-expanded={showAllCompetitions} aria-controls="competition-browser">
            {showAllCompetitions ? 'Close catalog' : `Browse all ${catalog.competitions.length}`}
          </Button>
        </div>
        <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 xl:grid-cols-6">
          {quickCompetitions.map((comp) => <CompetitionChoice key={comp.code} comp={comp} selected={comp.code === selectedComp} onSelect={() => handleSelectComp(comp.code)} />)}
        </div>
        {showAllCompetitions ? <div id="competition-browser" className="mt-3 rounded-2xl border border-surface1 bg-mantle/70 p-4">
          <label htmlFor="competition-search" className="text-sm font-semibold text-text">Find a league or cup</label>
          <Input id="competition-search" type="search" value={competitionSearch} onChange={(event) => setCompetitionSearch(event.target.value)} placeholder="Search competitions…" className="mt-2 w-full sm:max-w-sm" />
          {matchingCompetitions.length ? competitionGroups.map((group) => <section key={group} className="mt-5 first:mt-4">
            <h3 className="mb-2 text-xs font-semibold text-subtext1">{group}</h3>
            <div className="grid grid-cols-1 gap-2 sm:grid-cols-2 xl:grid-cols-4">
              {matchingCompetitions.filter((comp) => comp.group === group).map((comp) => <CompetitionChoice key={comp.code} comp={comp} selected={comp.code === selectedComp} onSelect={() => handleSelectComp(comp.code)} />)}
            </div>
          </section>) : <p className="mt-4 text-sm text-subtext0">No competition matches that search.</p>}
        </div> : null}
      </div>

      {/* 3. Controls & Filter Bar */}
      <Card className="p-4 rounded-2xl bg-surface0/70 border border-surface1/80 backdrop-blur-sm shadow-sm">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div className="flex flex-wrap items-center gap-4">
            {/* Season Selector */}
            <div className="flex items-center gap-2">
              <Calendar size={14} className="text-subtext0" />
              <span className="text-xs font-semibold text-subtext0 uppercase tracking-wide">Season:</span>
              <select
                value={selectedSeason}
                onChange={(e) => setSelectedSeason(Number(e.target.value))}
                className="px-3 py-1.5 rounded-lg bg-mantle border border-surface1 text-xs font-medium text-text focus:outline-none focus:border-blue cursor-pointer"
              >
                {availableSeasons.map((yr) => (
                  <option key={yr} value={yr}>
                    {selectedComp === 'WC' ? `${yr}` : `${yr}/${String(yr + 1).slice(-2)}`}
                    {yr === 2026 && ' (Live)'}
                  </option>
                ))}
              </select>
            </div>

            {/* Club Spotlight Selector */}
            <div className="flex items-center gap-2">
              <Shield size={14} className="text-subtext0" />
              <span className="text-xs font-semibold text-subtext0 uppercase tracking-wide">Club:</span>
              <select
                value={activeClub}
                onChange={(e) => setSelectedClub(e.target.value)}
                className="px-3 py-1.5 rounded-lg bg-mantle border border-surface1 text-xs font-medium text-text focus:outline-none focus:border-blue cursor-pointer max-w-[220px] truncate"
              >
                {availableClubs.length === 0 ? (
                  <option value="">Loading clubs...</option>
                ) : (
                  availableClubs.map((name) => (
                    <option key={name} value={name}>
                      {name}
                    </option>
                  ))
                )}
              </select>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <Link
              href={`/tables?competition=${selectedComp}&season=${selectedSeason}`}
              className="inline-flex items-center gap-1.5 text-xs font-semibold text-blue hover:text-lavender transition-colors"
            >
              <span>Full Standings</span>
              <ChevronRight size={14} />
            </Link>
          </div>
        </div>
      </Card>

      {/* 4. Club Spotlight & KPIs */}
      {spotlight && (
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
          {/* Spotlight Overview Card */}
          <Card className="lg:col-span-4 rounded-2xl bg-surface0 border border-surface1/80 p-6 flex flex-col justify-between relative overflow-hidden shadow-sm">
            {/* Background Ambient Glow */}
            <div className="absolute top-0 right-0 -mt-8 -mr-8 w-44 h-44 bg-blue/15 rounded-full blur-3xl pointer-events-none" />

            <div>
              <div className="flex items-center gap-4 mb-4">
                <FootballBadge
                  url={spotlight.team.badge_url}
                  name={spotlight.team.name}
                  size={58}
                />
                <div>
                  <div className="flex items-center gap-2">
                    <span className="text-xs font-bold uppercase tracking-wider text-blue">
                      Club Spotlight
                    </span>
                    <Chip size="sm" variant="soft" color="accent" className="font-mono text-xs">
                      {spotlight.season}/{String(spotlight.season + 1).slice(-2)}
                    </Chip>
                  </div>
                  <h3 className="text-2xl font-black text-text mt-1">
                    {spotlight.team.name}
                  </h3>
                  <p className="text-xs text-subtext0">
                    {currentComp?.name || selectedComp}
                  </p>
                </div>
              </div>

              {/* 4 Spotlight KPIs */}
              <div className="grid grid-cols-2 gap-3 mt-6">
                <div className="p-3.5 rounded-xl bg-mantle border border-surface1">
                  <span className="text-[10px] font-bold uppercase tracking-wider text-subtext0">
                    Matches Played
                  </span>
                  <p className="text-2xl font-black text-text mt-1">
                    {spotlight.played}
                  </p>
                </div>

                <div className="p-3.5 rounded-xl bg-mantle border border-surface1">
                  <span className="text-[10px] font-bold uppercase tracking-wider text-subtext0">
                    W – D – L Record
                  </span>
                  <p className="text-xl font-bold text-text mt-1">
                    <span className="text-green">{spotlight.wins}</span> -{' '}
                    <span className="text-yellow">{spotlight.draws}</span> -{' '}
                    <span className="text-red">{spotlight.losses}</span>
                  </p>
                </div>

                <div className="p-3.5 rounded-xl bg-mantle border border-surface1">
                  <span className="text-[10px] font-bold uppercase tracking-wider text-subtext0">
                    Points / Match
                  </span>
                  <p className={`text-2xl font-black mt-1 ${spotlight.points_per_game >= 2.0 ? 'text-teal' : 'text-blue'}`}>
                    {spotlight.points_per_game.toFixed(2)}
                  </p>
                </div>

                <div className="p-3.5 rounded-xl bg-mantle border border-surface1">
                  <span className="text-[10px] font-bold uppercase tracking-wider text-subtext0">
                    Goal Difference
                  </span>
                  <p className={`text-2xl font-black mt-1 ${spotlight.goal_difference >= 0 ? 'text-green' : 'text-red'}`}>
                    {spotlight.goal_difference > 0 ? `+${spotlight.goal_difference}` : spotlight.goal_difference}
                  </p>
                </div>
              </div>
            </div>

            <div className="mt-6 pt-4 border-t border-surface1 flex items-center justify-between text-xs text-subtext0">
              <span>Total Points: <strong className="text-text font-bold">{spotlight.points}</strong></span>
              <Link
                href={`/clubs?team=${encodeURIComponent(spotlight.team.name)}`}
                className="text-blue hover:underline font-semibold flex items-center gap-1"
              >
                <span>Club Lab deep dive</span>
                <ExternalLink size={12} />
              </Link>
            </div>
          </Card>

          {/* 3 Match Cards Strip (Latest, Previous, Next Fixture) */}
          <div className="lg:col-span-8 grid grid-cols-1 md:grid-cols-3 gap-4">
            {/* 1. Latest Completed Match */}
            <Card className="rounded-2xl bg-surface0 border border-surface1 p-4 flex flex-col justify-between shadow-sm">
              <div>
                <div className="flex items-center justify-between text-xs mb-3">
                  <span className="font-bold uppercase text-subtext0 tracking-wider flex items-center gap-1">
                    <Activity size={12} className="text-green" /> Latest Result
                  </span>
                  <span className="font-mono text-[11px] text-overlay1">
                    {spotlight.latest_match?.match_date || 'N/A'}
                  </span>
                </div>

                {spotlight.latest_match ? (
                  <div className="space-y-3">
                    <div className="flex items-center justify-between p-2.5 rounded-xl bg-mantle border border-surface1/60">
                      <div className="flex items-center gap-2.5 truncate">
                        <FootballBadge
                          url={spotlight.latest_match.home.badge_url}
                          name={spotlight.latest_match.home.name}
                          size={26}
                        />
                        <span className="text-xs font-semibold text-text truncate">
                          {spotlight.latest_match.home.name}
                        </span>
                      </div>
                      <span className="font-mono text-base font-black text-blue ml-2">
                        {spotlight.latest_match.home_goals}
                      </span>
                    </div>

                    <div className="flex items-center justify-between p-2.5 rounded-xl bg-mantle border border-surface1/60">
                      <div className="flex items-center gap-2.5 truncate">
                        <FootballBadge
                          url={spotlight.latest_match.away.badge_url}
                          name={spotlight.latest_match.away.name}
                          size={26}
                        />
                        <span className="text-xs font-semibold text-text truncate">
                          {spotlight.latest_match.away.name}
                        </span>
                      </div>
                      <span className="font-mono text-base font-black text-blue ml-2">
                        {spotlight.latest_match.away_goals}
                      </span>
                    </div>
                  </div>
                ) : (
                  <p className="text-xs text-subtext0 italic py-6 text-center">
                    No completed match recorded
                  </p>
                )}
              </div>

              {spotlight.latest_match?.referee && (
                <div className="mt-3 pt-2 border-t border-surface1 text-[10px] text-overlay1">
                  Ref: {spotlight.latest_match.referee}
                </div>
              )}
            </Card>

            {/* 2. Previous Match */}
            <Card className="rounded-2xl bg-surface0 border border-surface1 p-4 flex flex-col justify-between shadow-sm">
              <div>
                <div className="flex items-center justify-between text-xs mb-3">
                  <span className="font-bold uppercase text-subtext0 tracking-wider flex items-center gap-1">
                    <Activity size={12} className="text-blue" /> Previous Match
                  </span>
                  <span className="font-mono text-[11px] text-overlay1">
                    {spotlight.previous_match?.match_date || 'N/A'}
                  </span>
                </div>

                {spotlight.previous_match ? (
                  <div className="space-y-3">
                    <div className="flex items-center justify-between p-2.5 rounded-xl bg-mantle border border-surface1/60">
                      <div className="flex items-center gap-2.5 truncate">
                        <FootballBadge
                          url={spotlight.previous_match.home.badge_url}
                          name={spotlight.previous_match.home.name}
                          size={26}
                        />
                        <span className="text-xs font-semibold text-text truncate">
                          {spotlight.previous_match.home.name}
                        </span>
                      </div>
                      <span className="font-mono text-base font-black text-text ml-2">
                        {spotlight.previous_match.home_goals}
                      </span>
                    </div>

                    <div className="flex items-center justify-between p-2.5 rounded-xl bg-mantle border border-surface1/60">
                      <div className="flex items-center gap-2.5 truncate">
                        <FootballBadge
                          url={spotlight.previous_match.away.badge_url}
                          name={spotlight.previous_match.away.name}
                          size={26}
                        />
                        <span className="text-xs font-semibold text-text truncate">
                          {spotlight.previous_match.away.name}
                        </span>
                      </div>
                      <span className="font-mono text-base font-black text-text ml-2">
                        {spotlight.previous_match.away_goals}
                      </span>
                    </div>
                  </div>
                ) : (
                  <p className="text-xs text-subtext0 italic py-6 text-center">
                    No prior match recorded
                  </p>
                )}
              </div>

              {spotlight.previous_match?.competition && (
                <div className="mt-3 pt-2 border-t border-surface1 text-[10px] text-overlay1">
                  Comp: {spotlight.previous_match.competition}
                </div>
              )}
            </Card>

            {/* 3. Next Listed Fixture / ML Forecast */}
            <Card className="rounded-2xl bg-surface0 border border-surface1 p-4 flex flex-col justify-between shadow-sm relative overflow-hidden">
              <div className="absolute top-0 right-0 w-28 h-28 bg-mauve/15 rounded-full blur-2xl pointer-events-none" />

              <div>
                <div className="flex items-center justify-between text-xs mb-3">
                  <span className="font-bold uppercase text-mauve tracking-wider flex items-center gap-1">
                    <Zap size={12} className="text-yellow" /> Upcoming Forecast
                  </span>
                  <span className="font-mono text-[11px] text-overlay1">
                    {nextListedMatch?.match_date || 'Not listed'}
                  </span>
                </div>

                {nextListedMatch ? (
                  <div className="space-y-3">
                    <div className="flex items-center justify-between text-xs font-bold text-text">
                      <div className="flex items-center gap-2 truncate">
                        <FootballBadge
                          url={nextListedMatch.home.badge_url}
                          name={nextListedMatch.home.name}
                          size={22}
                        />
                        <span className="truncate">{nextListedMatch.home.name}</span>
                      </div>
                      <span className="text-subtext0 text-[10px] uppercase font-mono px-2 py-0.5 rounded bg-mantle">VS</span>
                      <div className="flex items-center gap-2 truncate justify-end">
                        <span className="truncate">{nextListedMatch.away.name}</span>
                        <FootballBadge
                          url={nextListedMatch.away.badge_url}
                          name={nextListedMatch.away.name}
                          size={22}
                        />
                      </div>
                    </div>

                    {spotlight.next_fixture ? <div className="space-y-1 mt-2">
                      <div className="flex justify-between text-[11px] font-mono text-subtext1">
                        <span className="text-blue">H: {(spotlight.next_fixture.home_probability * 100).toFixed(0)}%</span>
                        <span className="text-yellow">D: {(spotlight.next_fixture.draw_probability * 100).toFixed(0)}%</span>
                        <span className="text-peach">A: {(spotlight.next_fixture.away_probability * 100).toFixed(0)}%</span>
                      </div>
                      <div className="h-2.5 w-full rounded-full bg-mantle overflow-hidden flex">
                        <div
                          style={{ width: `${spotlight.next_fixture.home_probability * 100}%` }}
                          className="bg-blue h-full transition-all"
                          title={`Home Win: ${(spotlight.next_fixture.home_probability * 100).toFixed(1)}%`}
                        />
                        <div
                          style={{ width: `${spotlight.next_fixture.draw_probability * 100}%` }}
                          className="bg-yellow h-full transition-all"
                          title={`Draw: ${(spotlight.next_fixture.draw_probability * 100).toFixed(1)}%`}
                        />
                        <div
                          style={{ width: `${spotlight.next_fixture.away_probability * 100}%` }}
                          className="bg-peach h-full transition-all"
                          title={`Away Win: ${(spotlight.next_fixture.away_probability * 100).toFixed(1)}%`}
                        />
                      </div>
                    </div> : <p className="text-center text-[11px] text-subtext0">Listed fixture · prediction not available yet</p>}

                    {spotlight.next_fixture ? <div className="text-center pt-1">
                      <Chip size="sm" variant="soft" color="accent" className="text-[10px] font-bold uppercase tracking-wider">
                        Predicted: {spotlight.next_fixture.predicted_result}
                      </Chip>
                    </div> : null}
                  </div>
                ) : (
                  <div className="py-4 text-center">
                    <p className="text-xs text-subtext0 italic">
                      No scheduled fixture in forecast feed
                    </p>
                    <Link
                      href="/predictions"
                      className="inline-block text-xs text-blue hover:underline font-semibold mt-2"
                    >
                      View ML prediction board →
                    </Link>
                  </div>
                )}
              </div>

              <div className="mt-3 pt-2 border-t border-surface1 flex justify-between items-center text-[10px] text-overlay1">
                <span>Model: Softmax + Elo</span>
                <Link href="/predictions" className="text-blue hover:underline">
                  All Forecasts
                </Link>
              </div>
            </Card>
          </div>
        </div>
      )}

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
                  ? 'bg-surface1 text-blue shadow-sm'
                  : 'text-subtext0 hover:text-text'
              }`}
            >
              Performance Over Time
            </button>
            <button
              onClick={() => setChartView('matrix')}
              className={`px-3 py-1.5 rounded-lg font-semibold transition-colors cursor-pointer ${
                chartView === 'matrix'
                  ? 'bg-surface1 text-blue shadow-sm'
                  : 'text-subtext0 hover:text-text'
              }`}
            >
              Season Strength Map
            </button>
            <button
              onClick={() => setChartView('scatter')}
              className={`px-3 py-1.5 rounded-lg font-semibold transition-colors cursor-pointer ${
                chartView === 'scatter'
                  ? 'bg-surface1 text-blue shadow-sm'
                  : 'text-subtext0 hover:text-text'
              }`}
            >
              Attack vs Defense
            </button>
            <button
              onClick={() => setChartView('elo')}
              className={`px-3 py-1.5 rounded-lg font-semibold transition-colors cursor-pointer ${
                chartView === 'elo'
                  ? 'bg-surface1 text-blue shadow-sm'
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
                  <CartesianGrid strokeDasharray="3 3" stroke="#313244" vertical={false} />
                  <XAxis dataKey="season" stroke="#7f849c" fontSize={12} />
                  <YAxis domain={[0, 3]} stroke="#7f849c" fontSize={12} />
                  <RechartsTooltip
                    contentStyle={{
                      backgroundColor: '#181825',
                      borderColor: '#45475a',
                      borderRadius: '12px',
                      color: '#cdd6f4',
                      fontSize: '12px',
                    }}
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
                  <CartesianGrid strokeDasharray="3 3" stroke="#313244" />
                  <XAxis
                    type="number"
                    dataKey="goalsPerMatch"
                    name="Goals Scored"
                    unit=" G/M"
                    stroke="#7f849c"
                    fontSize={12}
                  />
                  <YAxis
                    type="number"
                    dataKey="concededPerMatch"
                    name="Goals Conceded"
                    unit=" G/M"
                    reversed
                    stroke="#7f849c"
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
                        fill={entry.club === activeClub ? '#89b4fa' : entry.ppg >= 2.0 ? '#94e2d5' : '#f38ba8'}
                        stroke="#ffffff"
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
                  <CartesianGrid strokeDasharray="3 3" stroke="#313244" vertical={false} />
                  <XAxis dataKey="season" stroke="#7f849c" fontSize={12} />
                  <YAxis domain={['auto', 'auto']} stroke="#7f849c" fontSize={12} />
                  <RechartsTooltip
                    contentStyle={{
                      backgroundColor: '#181825',
                      borderColor: '#45475a',
                      borderRadius: '12px',
                      color: '#cdd6f4',
                      fontSize: '12px',
                    }}
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

      {/* 6. Transfer Market Showcase (5 Biggest Competitions & Last 5 Seasons) */}
      <div ref={marketRef}>
      <Card className="rounded-2xl bg-surface0 border border-surface1/80 p-6 shadow-sm">
        <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4 border-b border-surface1/60 pb-5 mb-6">
          <div>
            <div className="flex items-center gap-2 mb-1">
              <ArrowRightLeft size={18} className="text-green" />
              <h2 className="text-lg font-bold text-text">
                Transfer Market Showcase
              </h2>
              <Chip size="sm" variant="soft" color="success" className="font-mono text-xs">
                30,000+ Deals
              </Chip>
            </div>
            <p className="text-xs text-subtext0">
              Top recorded transfers across the five biggest leagues, including the 2026/27 filter when source data is available.
            </p>
          </div>

          {/* Transfer Filters */}
          <div className="flex flex-wrap items-center gap-3">
            {/* Competition Filter */}
            <div className="flex items-center gap-2">
              <Shield size={14} className="text-subtext0" />
              <select
                value={transferComp}
                onChange={(e) => {
                  setTransferComp(e.target.value);
                  setTransferPage(1);
                }}
                className="px-3 py-1.5 rounded-lg bg-mantle border border-surface1 text-xs font-medium text-text focus:outline-none focus:border-blue cursor-pointer"
              >
                {BIG_5_COMPS.map((c) => (
                  <option key={c.code} value={c.code}>
                    {c.name}
                  </option>
                ))}
              </select>
            </div>

            {/* Season Filter */}
            <div className="flex items-center gap-2">
              <Calendar size={14} className="text-subtext0" />
              <select
                value={transferSeason}
                onChange={(e) => {
                  const val = e.target.value === 'all' ? 'all' : Number(e.target.value);
                  setTransferSeason(val);
                  setTransferPage(1);
                }}
                className="px-3 py-1.5 rounded-lg bg-mantle border border-surface1 text-xs font-medium text-text focus:outline-none focus:border-blue cursor-pointer"
              >
                {RECENT_TRANSFER_SEASONS.map((s) => (
                  <option key={s.value} value={s.value}>
                    {s.label}
                  </option>
                ))}
              </select>
            </div>
          </div>
        </div>

        {/* Transfers List */}
        {!marketVisible || isTransfersLoading ? (
          <LoadingSkeleton lines={5} />
        ) : paginatedTransfers.length > 0 ? (
          <div className="space-y-3">
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead className="border-b border-surface1 bg-mantle text-[11px] uppercase tracking-wider text-subtext0">
                  <tr>
                    <th className="py-3 px-4">Player</th>
                    <th className="py-3 px-4">From Club</th>
                    <th className="py-3 px-4 text-center">Movement</th>
                    <th className="py-3 px-4">To Club</th>
                    <th className="py-3 px-4 text-right">Transfer Fee</th>
                    <th className="py-3 px-4 text-right">Market Value</th>
                    <th className="py-3 px-4 text-right">Season / Date</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-surface1/50">
                  {paginatedTransfers.map((t) => (
                    <tr key={t.transfer_id} className="hover:bg-surface1/40 transition-colors">
                      <td className="py-3 px-4">
                        <div className="flex items-center gap-3">
                          <PlayerAvatar
                            image_url={t.image_url}
                            name={t.player_name}
                            size={44}
                            ring={true}
                          />
                          <div>
                            <p className="font-bold text-text text-sm hover:text-blue transition-colors">
                              {t.player_name}
                            </p>
                            <span className="text-[10px] text-subtext0 font-mono">
                              ID: {t.player_id}
                            </span>
                          </div>
                        </div>
                      </td>
                      <td className="py-3 px-4">
                        <div className="flex items-center gap-2">
                          <FootballBadge
                            url={t.from_club.badge_url}
                            name={t.from_club.name}
                            size={24}
                          />
                          <span className="text-subtext1 font-medium truncate max-w-[140px]">
                            {t.from_club.name}
                          </span>
                        </div>
                      </td>
                      <td className="py-3 px-4 text-center">
                        <div className="inline-flex items-center justify-center p-1.5 rounded-full bg-mantle text-green">
                          <ArrowRightLeft size={14} />
                        </div>
                      </td>
                      <td className="py-3 px-4">
                        <div className="flex items-center gap-2">
                          <FootballBadge
                            url={t.to_club.badge_url}
                            name={t.to_club.name}
                            size={24}
                          />
                          <span className="text-text font-bold truncate max-w-[140px]">
                            {t.to_club.name}
                          </span>
                        </div>
                      </td>
                      <td className="py-3 px-4 text-right font-mono">
                        {t.transfer_fee && t.transfer_fee > 0 ? (
                          <Chip size="sm" variant="soft" color="success" className="font-bold text-xs">
                            €{(t.transfer_fee / 1e6).toFixed(1)}M
                          </Chip>
                        ) : (
                          <span className="text-subtext0 italic">Free / Loan</span>
                        )}
                      </td>
                      <td className="py-3 px-4 text-right font-mono">
                        {t.market_value_eur && t.market_value_eur > 0 ? (
                          <Chip size="sm" variant="soft" color="accent" className="font-semibold text-[11px]">
                            €{(t.market_value_eur / 1e6).toFixed(0)}M
                          </Chip>
                        ) : (
                          <span className="text-overlay0">—</span>
                        )}
                      </td>
                      <td className="py-3 px-4 text-right font-mono text-[11px] text-subtext0">
                        <span className="px-2 py-0.5 rounded bg-surface1 text-subtext1 font-semibold mr-1.5">
                          {t.transfer_season}
                        </span>
                        <span>{t.transfer_date || ''}</span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {/* Pagination Controls (10 items per page) */}
            <div className="pt-4 border-t border-surface1 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 text-xs">
              <span className="text-subtext0 font-medium">
                Showing deals {(transferPage - 1) * transferPageSize + 1} to{' '}
                {Math.min(transferPage * transferPageSize, allTransfers.length)} of {allTransfers.length} loaded
              </span>

              <div className="flex items-center gap-2">
                <Button
                  size="sm"
                  variant="outline"
                  isDisabled={transferPage <= 1}
                  onPress={() => setTransferPage((p) => Math.max(1, p - 1))}
                  className="px-3 py-1.5 rounded-lg text-xs font-semibold cursor-pointer"
                >
                  <ChevronLeft size={14} className="mr-1 inline" /> Previous
                </Button>

                <span className="px-3 py-1 rounded bg-surface1 text-text font-mono text-xs">
                  Page {transferPage} of {totalTransferPages}
                </span>

                <Button
                  size="sm"
                  variant="outline"
                  isDisabled={transferPage >= totalTransferPages}
                  onPress={() => setTransferPage((p) => Math.min(totalTransferPages, p + 1))}
                  className="px-3 py-1.5 rounded-lg text-xs font-semibold cursor-pointer"
                >
                  Next <ChevronRight size={14} className="ml-1 inline" />
                </Button>
              </div>
            </div>
          </div>
        ) : (
          <p className="text-xs text-subtext0 italic text-center py-8">
            {transferSeason === 2026
              ? '2026/27 is ready in the interface, but the current Transfermarkt Open Dataset snapshot ends in July 2026 and contains no 2026/27 deals yet.'
              : 'No transfer deals found for the selected season or competition filters.'}
          </p>
        )}
      </Card>
      </div>

      {/* 7. Star Players Spotlight (Transfermarkt Snapshot) */}
      {starPlayersData?.players && starPlayersData.players.length > 0 && (
        <Card className="rounded-2xl bg-surface0 border border-surface1/80 p-6 shadow-sm">
          <div className="flex items-center justify-between mb-5">
            <div>
              <h2 className="text-lg font-bold text-text flex items-center gap-2">
                <Sparkles size={18} className="text-yellow" />
                World Star Players Spotlight
              </h2>
              <p className="text-xs text-subtext0">
                Highest market valuation stars with prominent player portraits & squad roles
              </p>
            </div>
            <Link
              href="/players"
              className="text-xs font-semibold text-blue hover:underline flex items-center gap-1"
            >
              <span>Explore 3,000+ Players</span>
              <ChevronRight size={14} />
            </Link>
          </div>

          <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-8 gap-3.5">
            {starPlayersData.players.map((p) => (
              <Link
                key={p.player_id}
                href={`/players?q=${encodeURIComponent(p.name)}`}
                className="group p-3.5 rounded-xl bg-mantle border border-surface1 hover:border-blue/60 transition-all flex flex-col items-center text-center shadow-xs hover:scale-[1.02]"
              >
                <div className="relative mb-2.5">
                  <PlayerAvatar
                    image_url={p.image_url}
                    name={p.name}
                    size={60}
                    ring={true}
                    className="group-hover:ring-blue"
                  />
                  <div className="absolute -bottom-1 -right-1 drop-shadow-md">
                    <FootballBadge
                      url={p.team.badge_url}
                      name={p.team.name}
                      size={20}
                    />
                  </div>
                </div>
                <p className="text-xs font-bold text-text truncate w-full group-hover:text-blue transition-colors">
                  {p.name}
                </p>
                <p className="text-[10px] text-subtext0 truncate w-full mt-0.5">
                  {p.position || 'Player'}
                </p>
                {p.market_value_eur && (
                  <Chip size="sm" variant="soft" color="success" className="mt-2 text-[10px] font-mono font-bold">
                    €{(p.market_value_eur / 1e6).toFixed(0)}M
                  </Chip>
                )}
              </Link>
            ))}
          </div>
        </Card>
      )}

      {/* 8. All 12 Supported Competitions Grid */}
      <div>
        <div className="flex items-center justify-between mb-4">
          <div>
            <h2 className="text-lg font-bold text-text flex items-center gap-2">
              <Shield size={18} className="text-sapphire" />
              Supported Tournaments & Domestic Leagues
            </h2>
            <p className="text-xs text-subtext0">
              Direct access to historical and live tables, fixtures and stats
            </p>
          </div>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
          {catalog.competitions.map((comp) => {
            const isTourney = comp.kind === 'tournament';
            const seasons = comp.seasons;
            const matchesCount = seasons.reduce((sum, s) => sum + s.match_count, 0);
            const liveSeason = seasons.find((s) => s.status === 'live_partial');

            return (
              <Link
                key={comp.code}
                href={
                  isTourney
                    ? `/tournaments?competition=${comp.code}`
                    : `/tables?competition=${comp.code}`
                }
                className="group rounded-2xl bg-surface0 border border-surface1 p-4 hover:border-blue/60 hover:bg-surface0/90 transition-all shadow-sm flex flex-col justify-between"
              >
                <div>
                  <div className="flex items-start justify-between gap-3 mb-3">
                    <CompetitionBadge
                      code={comp.code}
                      name={comp.name}
                      badge_url={comp.badge_url}
                      size={40}
                    />
                    <Chip
                      size="sm"
                      variant="soft"
                      color={isTourney ? 'warning' : liveSeason ? 'success' : 'default'}
                      className="text-[10px] font-bold uppercase tracking-wider"
                    >
                      {isTourney ? 'Tournament' : liveSeason ? 'Live Active' : 'Domestic'}
                    </Chip>
                  </div>

                  <h3 className="font-bold text-text text-sm group-hover:text-blue transition-colors">
                    {comp.name}
                  </h3>
                  <p className="text-xs text-subtext0 mt-0.5">
                    {seasons.length} {seasons.length === 1 ? 'season' : 'seasons'} recorded
                  </p>
                </div>

                <div className="mt-4 pt-3 border-t border-surface1/60 flex items-center justify-between text-xs text-subtext0">
                  <span className="font-mono">{matchesCount.toLocaleString()} matches</span>
                  <span className="text-blue group-hover:translate-x-0.5 transition-transform flex items-center gap-0.5">
                    Open <ChevronRight size={12} />
                  </span>
                </div>
              </Link>
            );
          })}
        </div>
      </div>
    </div>
  );
}

export default function OverviewPage() {
  return (
    <Suspense fallback={<LoadingSkeleton lines={10} />}>
      <OverviewContent />
    </Suspense>
  );
}
