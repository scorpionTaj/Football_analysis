'use client';

import { Suspense, useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import { api } from '@/lib/api/client';
import { queryKeys } from '@/lib/api/query-keys';
import { SourceBadge } from '@/components/ui/source-badge';
import { LoadingSkeleton, ErrorMessage } from '@/components/ui/loading';
import { PageHeader } from '@/components/ui/page-header';
import { PipelineHealth } from '@/components/pipeline-health';
import { usePagination } from '@/components/ui/pagination';
import { ShieldCheck, Database, Info, RefreshCw, FileCheck } from 'lucide-react';

function QualityContent() {
  const { data, isLoading, error, refetch } = useQuery({
    queryKey: queryKeys.quality,
    queryFn: () => api.quality(),
  });

  // Extract unique competitions and seasons for the matrix grid
  const grid = data?.grid;
  const { gridMatrix, uniqueSeasons, uniqueCompetitions } = useMemo(() => {
    if (!grid) return { gridMatrix: new Map(), uniqueSeasons: [], uniqueCompetitions: [] };
    const matrix = new Map<string, string>();
    const seasonsSet = new Set<number>();
    const compsSet = new Set<string>();

    for (const cell of grid) {
      matrix.set(`${cell.competition}_${cell.season}`, cell.status);
      seasonsSet.add(cell.season);
      compsSet.add(cell.competition);
    }

    return {
      gridMatrix: matrix,
      uniqueSeasons: Array.from(seasonsSet).sort((a, b) => a - b),
      uniqueCompetitions: Array.from(compsSet),
    };
  }, [grid]);

  type ChecksumRow = {
    league?: string;
    season?: number;
    row_count?: number;
    status?: string;
    sha256?: string;
    fetched_at?: string;
  };
  const checksums = useMemo(() => (data?.checksums || []) as ChecksumRow[], [data?.checksums]);
  const { paginatedItems: paginatedChecksums, paginationControls: ChecksumsPagination } = usePagination(checksums, 10);

  if (isLoading) return <LoadingSkeleton lines={10} />;
  if (error) {
    return <ErrorMessage title="Failed to load quality audit" detail={error.message} retry={() => refetch()} />;
  }
  if (!data) return null;

  return (
    <div className="space-y-6">
      {/* Top Status Banner */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 rounded-xl bg-surface0 border border-surface1 p-4">
        <div className="flex items-center gap-3">
          <div className="p-2.5 rounded-lg bg-green/10 text-green">
            <ShieldCheck className="h-5 w-5" />
          </div>
          <div>
            <h2 className="text-base font-bold text-text">Database Integrity & Freshness Audit</h2>
            <p className="text-xs text-subtext0 mt-0.5">
              Automated DuckDB validation, completeness matrix, null rate checks, and ingest run checksums.
            </p>
          </div>
        </div>
        <SourceBadge meta={data.source} />
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
        <div className="rounded-xl bg-surface0 border border-surface1 p-4">
          <p className="text-xs font-medium text-subtext0 uppercase">Historical Coverage</p>
          <div className="flex items-baseline gap-2 mt-1">
            <span className="text-2xl font-bold text-green">{data.completed_coverage}</span>
            <span className="text-xs text-subtext1">cells complete</span>
          </div>
        </div>

        <div className="rounded-xl bg-surface0 border border-surface1 p-4">
          <p className="text-xs font-medium text-subtext0 uppercase">Live Competitions</p>
          <div className="flex items-baseline gap-2 mt-1">
            <span className="text-2xl font-bold text-blue">{data.live_competitions}</span>
            <span className="text-xs text-subtext1">tracking partial</span>
          </div>
        </div>

        <div className="rounded-xl bg-surface0 border border-surface1 p-4">
          <p className="text-xs font-medium text-subtext0 uppercase">Match Records</p>
          <div className="flex items-baseline gap-2 mt-1">
            <span className="text-2xl font-bold text-text">{data.match_records.toLocaleString()}</span>
            <span className="text-xs text-subtext1">normalized rows</span>
          </div>
        </div>

        <div className="rounded-xl bg-surface0 border border-surface1 p-4">
          <p className="text-xs font-medium text-subtext0 uppercase">Impossible Shot Anomalies</p>
          <div className="flex items-baseline gap-2 mt-1">
            <span className="text-2xl font-bold text-green">{data.impossible_shot_rows}</span>
            <span className="text-xs text-green">clean (SOT &le; Shots)</span>
          </div>
        </div>
      </div>

      <div className="rounded-xl border border-surface1 bg-surface0 p-5 space-y-4">
        <h3 className="text-sm font-semibold text-text">Current-season, player and media coverage</h3>
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 xl:grid-cols-6">
          {[
            ['Recent competitions', data.recent_competitions.toLocaleString()],
            ['Completed live results', data.completed_results.toLocaleString()],
            ['Reference rows', data.reference_rows.toLocaleString()],
            ['Tracked players', data.tracked_players.toLocaleString()],
            ['Player clubs', data.player_clubs.toLocaleString()],
            ['Player stat rows', data.player_stat_rows.toLocaleString()],
            ['Cached artwork', data.artwork_rows.toLocaleString()],
          ].map(([label, value]) => (
            <div key={label} className="rounded-lg border border-surface1 bg-mantle p-3">
              <p className="text-[11px] uppercase text-subtext0">{label}</p>
              <p className="mt-1 text-xl font-bold text-text">{value}</p>
            </div>
          ))}
        </div>
      </div>

      <div className="rounded-xl border border-surface1 bg-surface0 p-5 space-y-3">
        <div>
          <h3 className="text-sm font-semibold text-text">Upcoming fixture coverage</h3>
          <p className="mt-1 text-xs text-subtext0">Future rows by source. Full-season calendars are provisional, and these counts are not completed results.</p>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full min-w-[560px] text-left text-xs">
            <thead className="border-b border-surface1 text-subtext0">
              <tr>
                <th className="py-2 pr-3">League</th>
                <th className="py-2 pr-3">Full calendar</th>
                <th className="py-2 pr-3">Weekly feed</th>
                <th className="py-2 pr-3">Next-event feed</th>
                <th className="py-2">Last fetched</th>
              </tr>
            </thead>
            <tbody>
              {(data.fixture_coverage || []).map((row) => (
                <tr key={row.competition} className="border-b border-surface1/60 last:border-0">
                  <td className="py-2 pr-3 font-semibold text-text">{row.competition}</td>
                  <td className="py-2 pr-3 text-teal">{row.full_schedule}</td>
                  <td className="py-2 pr-3 text-text">{row.weekly_window}</td>
                  <td className="py-2 pr-3 text-text">{row.next_listed}</td>
                  <td className="py-2 font-mono text-subtext0">{row.latest_fetched_at?.slice(0, 16).replace('T', ' ') || '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <div className="rounded-xl border border-surface1 bg-surface0 p-5 space-y-4">
          <h3 className="text-sm font-semibold text-text">Major tournament coverage</h3>
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
            <div className="rounded-lg bg-mantle p-3"><p className="text-xs text-subtext0">Matches</p><p className="text-xl font-bold text-blue">{data.tournament_matches.toLocaleString()}</p></div>
            <div className="rounded-lg bg-mantle p-3"><p className="text-xs text-subtext0">Teams</p><p className="text-xl font-bold text-teal">{data.tournament_teams.toLocaleString()}</p></div>
            {Object.entries(data.tournament_breakdown).map(([competition, count]) => (
              <div key={competition} className="rounded-lg bg-mantle p-3"><p className="text-xs text-subtext0">{competition}</p><p className="text-xl font-bold text-text">{count.toLocaleString()}</p></div>
            ))}
          </div>
        </div>
        <div className="rounded-xl border border-surface1 bg-surface0 p-5 space-y-4">
          <h3 className="text-sm font-semibold text-text">Extended source capabilities</h3>
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
            {[
              ['Context-rich matches', data.context_rich_matches],
              ['Match context rows', data.match_context_rows],
              ['Published formations', data.formation_rows],
              ['Published coaches', data.coach_rows],
              ['Tournament goals', data.tournament_goals],
              ['Detailed statistics', data.detailed_event_stats],
              ['Timeline events', data.timeline_events],
              ['Lineup rows', data.lineup_rows],
              ['Model predictions', data.model_predictions],
            ].map(([label, value]) => (
              <div key={String(label)} className="rounded-lg bg-mantle p-3"><p className="text-xs text-subtext0">{label}</p><p className="text-xl font-bold text-text">{Number(value).toLocaleString()}</p></div>
            ))}
          </div>
        </div>
      </div>

      {Object.keys(data.refresh_timestamps).length ? (
        <div className="rounded-xl border border-surface1 bg-surface0 p-5">
          <h3 className="mb-3 text-sm font-semibold text-text">Refresh timestamps</h3>
          <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-4">
            {Object.entries(data.refresh_timestamps).map(([source, timestamp]) => (
              <div key={source} className="flex items-center justify-between gap-3 rounded-lg bg-mantle px-3 py-2 text-xs"><span className="capitalize text-subtext0">{source.replaceAll('_', ' ')}</span><span className="font-mono text-text">{timestamp ? timestamp.slice(0, 16).replace('T', ' ') : '—'}</span></div>
            ))}
          </div>
        </div>
      ) : null}

      {/* Source Caps & Limitations */}
      <div className="rounded-xl border border-surface1 bg-surface0 p-5 space-y-3">
        <h3 className="text-sm font-semibold text-text flex items-center gap-2">
          <Info className="h-4 w-4 text-blue" /> Source Caps & Governance Notes
        </h3>
        <ul className="space-y-2 text-xs text-subtext1">
          {data.source_caps.map((cap, i) => (
            <li key={i} className="flex items-start gap-2">
              <span className="text-blue font-bold">·</span>
              <span>{cap}</span>
            </li>
          ))}
        </ul>
      </div>

      {/* Coverage Grid Matrix */}
      <div className="rounded-xl border border-surface1 bg-surface0 p-5 space-y-4">
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-semibold text-text flex items-center gap-2">
            <Database className="h-4 w-4 text-teal" /> Competition Coverage Matrix
          </h3>
          <div className="flex items-center gap-4 text-xs text-subtext0">
            <span className="flex items-center gap-1.5"><span className="h-2 w-2 rounded-full bg-green" /> Complete</span>
            <span className="flex items-center gap-1.5"><span className="h-2 w-2 rounded-full bg-yellow" /> Live Partial</span>
            <span className="flex items-center gap-1.5"><span className="h-2 w-2 rounded-full bg-surface2" /> Missing</span>
          </div>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-center text-xs">
            <thead className="border-b border-surface1 text-subtext0">
              <tr>
                <th className="py-2.5 px-3 text-left">League</th>
                {uniqueSeasons.map((year) => (
                  <th key={year} className="py-2.5 px-2 font-mono">
                    {year}/{String(year + 1).slice(2)}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-surface1">
              {uniqueCompetitions.map((comp) => (
                <tr key={comp} className="hover:bg-surface1/30">
                  <td className="py-2.5 px-3 text-left font-bold text-text">{comp}</td>
                  {uniqueSeasons.map((year) => {
                    const status = gridMatrix.get(`${comp}_${year}`) || 'missing';
                    const bg =
                      status === 'complete'
                        ? 'bg-green/15 text-green border-green/30'
                        : status === 'live_partial'
                        ? 'bg-yellow/15 text-yellow border-yellow/30'
                        : 'bg-surface1/50 text-overlay0 border-transparent';

                    return (
                      <td key={year} className="py-2 px-1">
                        <span className={`inline-block px-2 py-0.5 rounded text-[11px] font-medium border ${bg}`}>
                          {status === 'complete' ? '✓ Complete' : status === 'live_partial' ? '🔴 Live' : '—'}
                        </span>
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Null Rates Breakdown */}
      {data.null_coverage && Object.keys(data.null_coverage).length > 0 && (
        <div className="rounded-xl border border-surface1 bg-surface0 p-5 space-y-3">
          <h3 className="text-sm font-semibold text-text flex items-center gap-2">
            <FileCheck className="h-4 w-4 text-peach" /> Critical Metric Missingness (Null Rates)
          </h3>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 pt-1">
            {Object.entries(data.null_coverage).map(([col, rate]) => (
              <div key={col} className="rounded-lg bg-mantle p-3 border border-surface1">
                <p className="text-xs text-subtext0 font-mono">{col}</p>
                <p className="text-base font-bold text-text mt-1">
                  {(rate * 100).toFixed(2)}% <span className="text-xs text-subtext0 font-normal">null</span>
                </p>
              </div>
            ))}
          </div>
        </div>
      )}

      {data.shot_coverage.length ? (
        <div className="overflow-hidden rounded-xl border border-surface1 bg-surface0">
          <div className="border-b border-surface1 p-4"><h3 className="text-sm font-semibold text-text">Shot-field coverage</h3></div>
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="border-b border-surface1 bg-mantle uppercase text-subtext0"><tr><th className="px-4 py-3">Competition</th><th className="px-4 py-3">Season</th><th className="px-4 py-3 text-right">Matches</th><th className="px-4 py-3 text-right">Complete</th><th className="px-4 py-3 text-right">Coverage</th></tr></thead>
              <tbody className="divide-y divide-surface1">
                {data.shot_coverage.map((row) => <tr key={`${row.competition}-${row.season}`}><td className="px-4 py-3 font-semibold text-text">{row.competition}</td><td className="px-4 py-3 font-mono">{row.season}/{String(row.season + 1).slice(-2)}</td><td className="px-4 py-3 text-right">{row.matches}</td><td className="px-4 py-3 text-right">{row.shot_matches}</td><td className="px-4 py-3 text-right font-bold text-green">{row.coverage_pct.toFixed(1)}%</td></tr>)}
              </tbody>
            </table>
          </div>
        </div>
      ) : null}

      {/* Checksums & Ingestion Run Logs */}
      {data.checksums && data.checksums.length > 0 && (
        <div className="rounded-xl border border-surface1 bg-surface0 overflow-hidden">
          <div className="p-4 border-b border-surface1">
            <h3 className="text-sm font-semibold text-text flex items-center gap-2">
              <RefreshCw className="h-4 w-4 text-blue" /> Recent Ingestion Runs & Integrity Checksums
            </h3>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="border-b border-surface1 bg-mantle text-subtext0 uppercase">
                <tr>
                  <th className="py-2.5 px-4">League</th>
                  <th className="py-2.5 px-4">Season</th>
                  <th className="py-2.5 px-4">Rows</th>
                  <th className="py-2.5 px-4">Status</th>
                  <th className="py-2.5 px-4 font-mono">SHA-256 Digest</th>
                  <th className="py-2.5 px-4">Ingest Date</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-surface1">
                {paginatedChecksums.map((chk, i) => (
                  <tr key={i} className="hover:bg-surface1/30">
                    <td className="py-2 px-4 font-bold text-text">{chk.league}</td>
                    <td className="py-2 px-4 font-mono">{chk.season}</td>
                    <td className="py-2 px-4">{chk.row_count}</td>
                    <td className="py-2 px-4">
                      <span className="rounded bg-green/15 text-green px-2 py-0.5 text-[10px] font-bold uppercase">
                        {chk.status}
                      </span>
                    </td>
                    <td className="py-2 px-4 font-mono text-[11px] text-overlay1 truncate max-w-[200px]">
                      {chk.sha256 || 'n/a'}
                    </td>
                    <td className="py-2 px-4 text-subtext0">{chk.fetched_at?.slice(0, 16) || '-'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="px-4 py-3 bg-mantle border-t border-surface1">
            {ChecksumsPagination}
          </div>
        </div>
      )}
    </div>
  );
}

export default function QualityPage() {
  return (
    <div className="space-y-6">
      <PageHeader icon={ShieldCheck} eyebrow="Trust and provenance" title="Data Quality & Observability" description="See coverage, freshness, source constraints and ingestion evidence before relying on an analysis." />

      <PipelineHealth />

      <Suspense fallback={<LoadingSkeleton lines={10} />}>
        <QualityContent />
      </Suspense>
    </div>
  );
}
