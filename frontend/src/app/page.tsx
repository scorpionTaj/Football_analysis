'use client';

import React, { Suspense, useMemo, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import Link from 'next/link';
import { api } from '@/lib/api/client';
import { queryKeys } from '@/lib/api/query-keys';
import { SourceBadge } from '@/components/ui/source-badge';
import { LoadingSkeleton, ErrorMessage } from '@/components/ui/loading';
import { FootballBadge, CompetitionBadge } from '@/lib/media-utils';
import { fuzzySort } from '@/lib/fuzzy';
import { BIG_5_COMPS, MarketSection } from '@/components/overview/market-section';
import { ClubTrends } from '@/components/overview/club-trends';
import type { Competition } from '@/lib/api/types';
import {
  Card,
  Chip,
  Button,
  Input,
} from '@heroui/react';
import {
  Trophy,
  Activity,
  Calendar,
  Shield,
  Zap,
  ChevronRight,
  ExternalLink,
} from 'lucide-react';

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
  const [pickedSeason, setSelectedSeason] = useState<number | null>(null);
  const [selectedClub, setSelectedClub] = useState<string>('');
  const [showAllCompetitions, setShowAllCompetitions] = useState(false);
  const [competitionSearch, setCompetitionSearch] = useState('');

  // 1. Fetch Catalog
  const { data: catalog, isLoading: isCatalogLoading, error: catalogError, refetch: refetchCatalog } = useQuery({
    queryKey: queryKeys.catalog,
    queryFn: () => api.catalog(),
  });

  // Current active competition object
  const currentComp = useMemo(() => {
    return catalog?.competitions.find((c) => c.code === selectedComp);
  }, [catalog, selectedComp]);

  // Available seasons for this competition (sorted newest first)
  const availableSeasons = useMemo(() => {
    if (!currentComp) return [];
    return [...currentComp.seasons.map((s) => s.season)].sort((a, b) => b - a);
  }, [currentComp]);
  // Default to the competition's latest season from the catalog, not a hard-coded year.
  const selectedSeason = pickedSeason ?? availableSeasons[0] ?? catalog?.current_season;

  // 2. Fetch Health
  const { data: health } = useQuery({
    queryKey: queryKeys.health,
    queryFn: () => api.health(),
  });

  // 3. Fetch Teams in this competition & season (to populate all real clubs)
  const { data: teamsData } = useQuery({
    queryKey: queryKeys.teams(selectedComp, selectedSeason),
    queryFn: () => api.teams(selectedComp, selectedSeason),
    enabled: Boolean(selectedComp) && selectedSeason != null,
  });

  // 4. Fetch Overview Spotlight & Trends
  const { data: overviewData, error: overviewError, refetch: refetchOverview } = useQuery({
    queryKey: queryKeys.overview({ team: selectedClub || undefined, competition: selectedComp, season: selectedSeason }),
    queryFn: () => api.overview({ team: selectedClub || undefined, competition: selectedComp, season: selectedSeason }),
    enabled: selectedSeason != null,
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

      {overviewError ? (
        <ErrorMessage title="Overview unavailable" detail={overviewError.message} retry={() => refetchOverview()} />
      ) : null}

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
              <Calendar size={14} className="text-subtext0" aria-hidden="true" />
              <label htmlFor="overview-season" className="text-xs font-semibold text-subtext0 uppercase tracking-wide">Season:</label>
              <select
                id="overview-season"
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
              <Shield size={14} className="text-subtext0" aria-hidden="true" />
              <label htmlFor="overview-club" className="text-xs font-semibold text-subtext0 uppercase tracking-wide">Club:</label>
              <select
                id="overview-club"
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
                <span>Model: walk-forward champion</span>
                <Link href="/predictions" className="text-blue hover:underline">
                  All Forecasts
                </Link>
              </div>
            </Card>
          </div>
        </div>
      )}

      <ClubTrends
        overviewData={overviewData}
        selectedComp={selectedComp}
        selectedSeason={selectedSeason}
        availableSeasons={availableSeasons}
        activeClub={activeClub}
        currentComp={currentComp}
      />

      <MarketSection />

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
