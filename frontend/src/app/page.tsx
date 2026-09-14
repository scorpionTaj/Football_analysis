'use client';

import { useQuery } from '@tanstack/react-query';
import { api } from '@/lib/api/client';
import { queryKeys } from '@/lib/api/query-keys';
import { SourceBadge } from '@/components/ui/source-badge';
import { LoadingSkeleton, ErrorMessage } from '@/components/ui/loading';
import type { Competition } from '@/lib/api/types';
import { Suspense } from 'react';

function OverviewContent() {
  const { data: catalog, isLoading, error, refetch } = useQuery({
    queryKey: queryKeys.catalog,
    queryFn: () => api.catalog(),
  });

  const { data: health } = useQuery({
    queryKey: queryKeys.health,
    queryFn: () => api.health(),
  });

  if (isLoading) return <LoadingSkeleton lines={8} />;
  if (error) {
    return (
      <ErrorMessage
        title="Failed to load catalog"
        detail={error.message}
        retry={() => refetch()}
      />
    );
  }
  if (!catalog) return null;

  const domestic = catalog.competitions.filter((c) => c.kind === 'domestic');
  const tournaments = catalog.competitions.filter((c) => c.kind === 'tournament');
  const totalMatches = catalog.competitions
    .flatMap((c) => c.seasons)
    .reduce((sum, s) => sum + s.match_count, 0);
  const liveSeasons = catalog.competitions
    .flatMap((c) => c.seasons)
    .filter((s) => s.status === 'live_partial').length;

  return (
    <>
      {/* Status bar */}
      <div className="flex flex-wrap items-center gap-4 mb-8">
        <div className="flex items-center gap-2">
          <span
            className={`h-2.5 w-2.5 rounded-full ${
              health?.status === 'ok' ? 'bg-green' : 'bg-red'
            }`}
          />
          <span className="text-sm text-subtext0">
            API {health?.status ?? 'checking…'}
          </span>
        </div>
        <SourceBadge meta={catalog.source} />
      </div>

      {/* Metrics grid */}
      <div className="grid grid-cols-2 gap-4 sm:grid-cols-4 mb-8">
        <MetricCard label="Competitions" value={catalog.competitions.length} />
        <MetricCard label="Total Matches" value={totalMatches.toLocaleString()} />
        <MetricCard label="Current Season" value={catalog.current_season} />
        <MetricCard label="Live Seasons" value={liveSeasons} accent />
      </div>

      {/* Leagues */}
      <section className="mb-8">
        <h2 className="text-lg font-semibold text-text mb-4">
          Domestic Leagues
        </h2>
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {domestic.map((comp) => (
            <CompetitionCard key={comp.code} competition={comp} />
          ))}
        </div>
      </section>

      {/* Tournaments */}
      <section>
        <h2 className="text-lg font-semibold text-text mb-4">
          Tournaments
        </h2>
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {tournaments.map((comp) => (
            <CompetitionCard key={comp.code} competition={comp} />
          ))}
        </div>
      </section>
    </>
  );
}

function MetricCard({
  label,
  value,
  accent = false,
}: {
  label: string;
  value: string | number;
  accent?: boolean;
}) {
  return (
    <div className="rounded-xl bg-surface0 p-4 border border-surface1">
      <p className="text-xs font-medium text-subtext0 uppercase tracking-wide">
        {label}
      </p>
      <p
        className={`mt-1 text-2xl font-bold ${accent ? 'text-blue' : 'text-text'}`}
      >
        {value}
      </p>
    </div>
  );
}

function CompetitionCard({ competition }: { competition: Competition }) {
  const seasons = competition.seasons;
  const totalMatches = seasons.reduce((s, r) => s + r.match_count, 0);
  const latest = seasons.at(-1);

  return (
    <div className="rounded-xl bg-surface0 border border-surface1 p-4 hover:border-surface2 transition-colors">
      <div className="flex items-center gap-2 mb-2">
        <span className="text-base" aria-hidden="true">
          {competition.kind === 'tournament' ? '🏆' : '⚽'}
        </span>
        <h3 className="font-semibold text-text">{competition.name}</h3>
      </div>
      <div className="flex flex-wrap gap-x-4 gap-y-1 text-sm text-subtext0">
        <span>{seasons.length} seasons</span>
        <span>{totalMatches.toLocaleString()} matches</span>
        {latest && (
          <span className={latest.status === 'live_partial' ? 'text-green' : ''}>
            {latest.label}
            {latest.status === 'live_partial' && ' 🔴'}
          </span>
        )}
      </div>
    </div>
  );
}

export default function OverviewPage() {
  return (
    <>
      <h1 className="text-2xl font-bold text-text mb-6">Overview</h1>
      <Suspense fallback={<LoadingSkeleton lines={8} />}>
        <OverviewContent />
      </Suspense>
    </>
  );
}
