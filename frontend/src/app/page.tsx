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
import type { Competition, Match, TeamRef } from '@/lib/api/types';
import { Button, Input } from '@heroui/react';
import { Activity, ChevronRight, ExternalLink, Zap } from 'lucide-react';
import { PageHeader } from '@/components/ui/page-header';
import { Panel } from '@/components/ui/panel';
import { Stat } from '@/components/ui/stat';
import { Chip } from '@/components/ui/chip';
import { Select } from '@/components/ui/select';
import { ProbabilityBar } from '@/components/ui/probability-bar';

function CompetitionChoice({ comp, selected, onSelect }: { comp: Competition; selected: boolean; onSelect: () => void }) {
  return (
    <button
      type="button"
      onClick={onSelect}
      aria-pressed={selected}
      className={`flex min-h-11 min-w-0 items-center gap-2 rounded-lg border px-3 py-2 text-left text-[13px] font-medium transition-colors ${selected
        ? 'border-accent bg-accent/10 text-text'
        : 'border-surface1 text-subtext0 hover:border-surface2 hover:text-text'}`}
    >
      <CompetitionBadge code={comp.code} name={comp.name} badge_url={comp.badge_url} size={22} />
      <span className="min-w-0 break-words">{comp.name}</span>
      {comp.kind === 'tournament' ? <Chip tone="warning" className="ml-auto">Cup</Chip> : null}
    </button>
  );
}

function TeamLine({ team, goals }: { team: TeamRef; goals?: number | null }) {
  return (
    <div className="flex items-center justify-between gap-2">
      <span className="flex min-w-0 items-center gap-2">
        <FootballBadge url={team.badge_url} name={team.name} size={22} />
        <span className="truncate text-[13px] text-text">{team.name}</span>
      </span>
      {goals !== undefined ? <span className="text-base font-semibold tabular-nums text-text">{goals ?? '–'}</span> : null}
    </div>
  );
}

function ScoreCard({ title, match, footer, empty }: { title: string; match?: Match | null; footer?: string; empty: string }) {
  return (
    <Panel bodyClassName="flex h-full flex-col">
      <div className="mb-3 flex items-center justify-between text-xs">
        <span className="font-medium text-text">{title}</span>
        <span className="tabular-nums text-subtext0">{match?.match_date || 'N/A'}</span>
      </div>
      {match ? (
        <div className="space-y-2.5">
          <TeamLine team={match.home} goals={match.home_goals} />
          <TeamLine team={match.away} goals={match.away_goals} />
        </div>
      ) : <p className="py-6 text-center text-xs text-subtext0">{empty}</p>}
      {footer ? <p className="mt-auto truncate border-t border-surface1 pt-2 text-xs text-subtext0">{footer}</p> : null}
    </Panel>
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

  const seasonLabel = (yr: number) => {
    const live = currentComp?.seasons.find((season) => season.season === yr)?.status === 'live_partial';
    return `${selectedComp === 'WC' ? yr : `${yr}/${String(yr + 1).slice(-2)}`}${live ? ' (Live)' : ''}`;
  };

  return (
    <div className="space-y-6 pb-12">
      <PageHeader
        icon={Activity}
        eyebrow="Matchday workspace"
        title="Football intelligence, from fixture to forecast"
        description="Explore sourced fixtures, club form, players and model forecasts in one place."
        action={<>
          <span className="inline-flex items-center gap-1.5 rounded-md border border-surface1 px-2 py-0.5 text-xs text-subtext0">
            <span className={`size-1.5 rounded-full ${health?.status === 'ok' ? 'bg-positive' : 'bg-negative'}`} aria-hidden="true" />
            API {health?.status ?? 'connecting'} · {totalMatches.toLocaleString()} matches · {catalog.competitions.length} competitions
          </span>
          {overviewData?.source && <SourceBadge meta={overviewData.source} />}
        </>}
      />

      {overviewError ? (
        <ErrorMessage title="Overview unavailable" detail={overviewError.message} retry={() => refetchOverview()} />
      ) : null}

      <Panel
        title="Choose a competition"
        actions={<Button size="sm" variant="outline" onPress={() => setShowAllCompetitions((open) => !open)} aria-expanded={showAllCompetitions} aria-controls="competition-browser">
          {showAllCompetitions ? 'Close catalog' : `Browse all ${catalog.competitions.length}`}
        </Button>}
      >
        <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 xl:grid-cols-6">
          {quickCompetitions.map((comp) => <CompetitionChoice key={comp.code} comp={comp} selected={comp.code === selectedComp} onSelect={() => handleSelectComp(comp.code)} />)}
        </div>
        {showAllCompetitions ? <div id="competition-browser" className="mt-4 border-t border-surface1 pt-4">
          <label htmlFor="competition-search" className="text-[13px] font-medium text-text">Find a league or cup</label>
          <Input id="competition-search" type="search" value={competitionSearch} onChange={(event) => setCompetitionSearch(event.target.value)} placeholder="Search competitions…" className="mt-2 w-full sm:max-w-sm" />
          {matchingCompetitions.length ? competitionGroups.map((group) => <section key={group} className="mt-4">
            <h3 className="mb-2 text-xs font-medium text-subtext0">{group}</h3>
            <div className="grid grid-cols-1 gap-2 sm:grid-cols-2 xl:grid-cols-4">
              {matchingCompetitions.filter((comp) => comp.group === group).map((comp) => <CompetitionChoice key={comp.code} comp={comp} selected={comp.code === selectedComp} onSelect={() => handleSelectComp(comp.code)} />)}
            </div>
          </section>) : <p className="mt-4 text-sm text-subtext0">No competition matches that search.</p>}
        </div> : null}
      </Panel>

      <div className="flex flex-wrap items-end justify-between gap-3">
        <div className="grid w-full grid-cols-2 gap-3 sm:flex sm:w-auto">
          <Select
            label="Season"
            value={selectedSeason == null ? '' : String(selectedSeason)}
            onChange={(value) => setSelectedSeason(Number(value))}
            options={availableSeasons.map((yr) => ({ value: String(yr), label: seasonLabel(yr) }))}
            className="sm:w-40"
          />
          <Select
            label="Club"
            value={activeClub}
            onChange={setSelectedClub}
            options={availableClubs.map((name) => ({ value: name, label: name }))}
            placeholder={availableClubs.length ? undefined : 'Loading clubs…'}
            className="sm:w-56"
          />
        </div>
        <Link href={`/tables?competition=${selectedComp}&season=${selectedSeason}`} className="inline-flex items-center gap-1 text-[13px] font-medium text-accent hover:underline">
          Full standings <ChevronRight className="size-4" aria-hidden="true" />
        </Link>
      </div>

      {spotlight && (
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-12">
          <Panel className="lg:col-span-4" bodyClassName="flex h-full flex-col">
            <div className="flex items-center gap-3">
              <FootballBadge url={spotlight.team.badge_url} name={spotlight.team.name} size={44} />
              <div className="min-w-0">
                <p className="text-xs text-subtext0">Club spotlight · {currentComp?.name || selectedComp} · {seasonLabel(spotlight.season)}</p>
                <h2 className="truncate text-lg font-semibold text-text">{spotlight.team.name}</h2>
              </div>
            </div>
            <div className="mt-4 grid grid-cols-2 gap-2">
              <Stat inset label="Matches played" value={spotlight.played} />
              <Stat inset label="W – D – L" value={<span className="text-xl">
                <span className="text-positive">{spotlight.wins}</span>
                <span className="text-overlay0"> – </span>{spotlight.draws}
                <span className="text-overlay0"> – </span><span className="text-negative">{spotlight.losses}</span>
              </span>} />
              <Stat inset label="Points / match" value={spotlight.points_per_game.toFixed(2)} />
              <Stat inset label="Goal difference" tone={spotlight.goal_difference >= 0 ? 'positive' : 'negative'}
                value={spotlight.goal_difference > 0 ? `+${spotlight.goal_difference}` : spotlight.goal_difference} />
            </div>
            <div className="mt-auto flex items-center justify-between border-t border-surface1 pt-3 text-xs text-subtext0">
              <span>Total points <strong className="font-semibold text-text tabular-nums">{spotlight.points}</strong></span>
              <Link href={`/clubs?team=${encodeURIComponent(spotlight.team.name)}`} className="inline-flex items-center gap-1 font-medium text-accent hover:underline">
                Club Lab deep dive <ExternalLink className="size-3" aria-hidden="true" />
              </Link>
            </div>
          </Panel>

          <div className="grid grid-cols-1 gap-4 md:grid-cols-3 lg:col-span-8">
            <ScoreCard title="Latest result" match={spotlight.latest_match} footer={spotlight.latest_match?.referee ? `Referee: ${spotlight.latest_match.referee}` : undefined} empty="No completed match recorded" />
            <ScoreCard title="Previous match" match={spotlight.previous_match} footer={spotlight.previous_match?.competition ? `Competition: ${spotlight.previous_match.competition}` : undefined} empty="No prior match recorded" />
            <Panel bodyClassName="flex h-full flex-col">
              <div className="mb-3 flex items-center justify-between text-xs">
                <span className="inline-flex items-center gap-1 font-medium text-text"><Zap className="size-3.5 text-accent" aria-hidden="true" /> Upcoming forecast</span>
                <span className="tabular-nums text-subtext0">{nextListedMatch?.match_date || 'Not listed'}</span>
              </div>
              {nextListedMatch ? (
                <div className="space-y-3">
                  <TeamLine team={nextListedMatch.home} />
                  <TeamLine team={nextListedMatch.away} />
                  {spotlight.next_fixture ? (
                    <>
                      <ProbabilityBar home={spotlight.next_fixture.home_probability} draw={spotlight.next_fixture.draw_probability} away={spotlight.next_fixture.away_probability} />
                      <p className="text-xs text-subtext0">Model pick: <span className="font-medium text-text">{spotlight.next_fixture.predicted_result}</span></p>
                    </>
                  ) : <p className="text-xs text-subtext0">Listed fixture · prediction not available yet</p>}
                </div>
              ) : (
                <p className="py-4 text-center text-xs text-subtext0">No scheduled fixture in the forecast feed</p>
              )}
              <div className="mt-auto flex items-center justify-between border-t border-surface1 pt-3 text-xs text-subtext0">
                <span>Walk-forward champion</span>
                <Link href="/predictions" className="font-medium text-accent hover:underline">All forecasts</Link>
              </div>
            </Panel>
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

      <Panel title="Leagues and tournaments" description="Historical and live tables, fixtures and stats for every covered competition" bodyClassName="p-0">
        <ul className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
          {catalog.competitions.map((comp) => {
            const isTourney = comp.kind === 'tournament';
            const matchesCount = comp.seasons.reduce((sum, season) => sum + season.match_count, 0);
            const live = comp.seasons.some((season) => season.status === 'live_partial');
            return (
              <li key={comp.code} className="border-b border-surface1 sm:border-r">
                <Link href={isTourney ? `/tournaments?competition=${comp.code}` : `/tables?competition=${comp.code}`}
                  className="group flex items-center gap-3 px-4 py-3 transition-colors hover:bg-surface1/40">
                  <CompetitionBadge code={comp.code} name={comp.name} badge_url={comp.badge_url} size={28} />
                  <span className="min-w-0 flex-1">
                    <span className="block truncate text-[13px] font-medium text-text group-hover:text-accent">{comp.name}</span>
                    <span className="block text-xs tabular-nums text-subtext0">{comp.seasons.length} {comp.seasons.length === 1 ? 'season' : 'seasons'} · {matchesCount.toLocaleString()} matches</span>
                  </span>
                  {isTourney ? <Chip tone="warning">Cup</Chip> : live ? <Chip tone="positive">Live</Chip> : null}
                </Link>
              </li>
            );
          })}
        </ul>
      </Panel>
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
