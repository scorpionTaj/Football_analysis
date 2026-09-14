'use client';

import { Suspense, useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import { api } from '@/lib/api/client';
import { queryKeys } from '@/lib/api/query-keys';
import { SourceBadge } from '@/components/ui/source-badge';
import { LoadingSkeleton, ErrorMessage } from '@/components/ui/loading';
import { usePagination } from '@/components/ui/pagination';
import { ShieldCheck, CheckCircle, AlertTriangle, Database, Info, RefreshCw, FileCheck } from 'lucide-react';

export function QualityContent() {
  const { data, isLoading, error, refetch } = useQuery({
    queryKey: queryKeys.quality,
    queryFn: () => api.quality(),
  });

  // Extract unique competitions and seasons for the matrix grid
  const { gridMatrix, uniqueSeasons, uniqueCompetitions } = useMemo(() => {
    if (!data?.grid) return { gridMatrix: new Map(), uniqueSeasons: [], uniqueCompetitions: [] };
    const matrix = new Map<string, string>();
    const seasonsSet = new Set<number>();
    const compsSet = new Set<string>();

    for (const cell of data.grid) {
      matrix.set(`${cell.competition}_${cell.season}`, cell.status);
      seasonsSet.add(cell.season);
      compsSet.add(cell.competition);
    }

    return {
      gridMatrix: matrix,
      uniqueSeasons: Array.from(seasonsSet).sort((a, b) => a - b),
      uniqueCompetitions: Array.from(compsSet),
    };
  }, [data?.grid]);

  const checksums = useMemo(() => data?.checksums || [], [data?.checksums]);
  const { paginatedItems: paginatedChecksums, PaginationComponent: ChecksumsPagination } = usePagination(checksums, 10);

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
                {paginatedChecksums.map((chk: any, i: number) => (
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
            <ChecksumsPagination />
          </div>
        </div>
      )}
    </div>
  );
}

export default function QualityPage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-text tracking-tight">Data Quality & Ingestion Observability</h1>
        <p className="text-sm text-subtext0 mt-1">
          Historical partition completeness, free-tier source constraints, schema validation, and SHA-256 audit logs.
        </p>
      </div>

      <Suspense fallback={<LoadingSkeleton lines={10} />}>
        <QualityContent />
      </Suspense>
    </div>
  );
}
