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
import { ShieldCheck } from 'lucide-react';
import { Panel } from '@/components/ui/panel';
import { Stat } from '@/components/ui/stat';
import { Chip } from '@/components/ui/chip';
import { DataTable, SortTh, TableFilter, TBody, THead, Td, Th } from '@/components/ui/data-table';
import { useTableView } from '@/lib/hooks/use-table-view';
import { CompetitionBadge } from '@/lib/media-utils';

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
  const runTable = useTableView(checksums, {
    columns: { league: (r) => r.league, season: (r) => r.season, rows: (r) => r.row_count, status: (r) => r.status, fetched: (r) => r.fetched_at },
    initial: { key: 'fetched', dir: 'desc' },
    search: (r) => [r.league, r.status, String(r.season ?? '')],
  });
  const { paginatedItems: paginatedChecksums, paginationControls: ChecksumsPagination } = usePagination(runTable.rows, 10);

  if (isLoading) return <LoadingSkeleton lines={10} />;
  if (error) {
    return <ErrorMessage title="Failed to load quality audit" detail={error.message} retry={() => refetch()} />;
  }
  if (!data) return null;

  const n = (value: number | string) => Number(value).toLocaleString();
  const ts = (value: string | null | undefined) => (value ? value.slice(0, 16).replace('T', ' ') : '—');
  const counts = (rows: [string, number | string][]) => (
    <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
      {rows.map(([label, value]) => <Stat key={label} inset label={label} value={n(value)} />)}
    </div>
  );

  return (
    <div className="space-y-4">
      <Panel
        title="Database integrity and freshness audit"
        description="Automated DuckDB validation, completeness matrix, null-rate checks and ingest run checksums."
        actions={<SourceBadge meta={data.source} />}
      >
        <div className="grid grid-cols-2 gap-2 md:grid-cols-4">
          <Stat inset label="Historical coverage" value={data.completed_coverage} hint="cells complete" />
          <Stat inset label="Live competitions" value={data.live_competitions} hint="tracking partial" />
          <Stat inset label="Match records" value={n(data.match_records)} hint="normalised rows" />
          <Stat inset label="Impossible shot rows" value={data.impossible_shot_rows}
            tone={data.impossible_shot_rows ? 'warning' : 'positive'}
            hint={data.impossible_shot_rows ? 'quarantined (SOT > shots)' : 'clean (SOT ≤ shots)'} />
        </div>
      </Panel>

      <Panel title="Current-season, player and media coverage">
        <div className="grid grid-cols-2 gap-2 sm:grid-cols-4 xl:grid-cols-7">
          {([
            ['Recent competitions', data.recent_competitions],
            ['Completed live results', data.completed_results],
            ['Reference rows', data.reference_rows],
            ['Tracked players', data.tracked_players],
            ['Player clubs', data.player_clubs],
            ['Player stat rows', data.player_stat_rows],
            ['Cached artwork', data.artwork_rows],
          ] as [string, number][]).map(([label, value]) => <Stat key={label} inset label={label} value={n(value)} />)}
        </div>
      </Panel>

      <Panel title="Upcoming fixture coverage" description="Future rows by source. Full-season calendars are provisional, and these counts are not completed results." bodyClassName="p-0">
        <DataTable minWidth={560} caption="Upcoming fixture coverage">
          <THead><tr><Th>League</Th><Th align="right">Full calendar</Th><Th align="right">Weekly feed</Th><Th align="right">Next-event feed</Th><Th>Last fetched</Th></tr></THead>
          <TBody>
            {(data.fixture_coverage || []).map((row) => (
              <tr key={row.competition}>
<Td><span className="flex items-center gap-2 font-medium"><CompetitionBadge code={row.competition} name={row.competition} size={18} />{row.competition}</span></Td>
                <Td align="right">{row.full_schedule}</Td>
                <Td align="right" className="text-subtext1">{row.weekly_window}</Td>
                <Td align="right" className="text-subtext1">{row.next_listed}</Td>
                <Td className="text-subtext0">{ts(row.latest_fetched_at)}</Td>
              </tr>
            ))}
          </TBody>
        </DataTable>
      </Panel>

      <div className="grid gap-4 lg:grid-cols-2">
        <Panel title="Major tournament coverage">
          {counts([
            ['Matches', data.tournament_matches],
            ['Teams', data.tournament_teams],
            ...Object.entries(data.tournament_breakdown) as [string, number][],
          ])}
        </Panel>
        <Panel title="Extended source capabilities">
          {counts([
            ['Context-rich matches', data.context_rich_matches],
            ['Match context rows', data.match_context_rows],
            ['Published formations', data.formation_rows],
            ['Published coaches', data.coach_rows],
            ['Tournament goals', data.tournament_goals],
            ['Detailed statistics', data.detailed_event_stats],
            ['Timeline events', data.timeline_events],
            ['Lineup rows', data.lineup_rows],
            ['Model predictions', data.model_predictions],
          ])}
        </Panel>
      </div>

      {Object.keys(data.refresh_timestamps).length ? (
        <Panel title="Refresh timestamps">
          <dl className="grid gap-x-6 gap-y-2 sm:grid-cols-2 lg:grid-cols-4">
            {Object.entries(data.refresh_timestamps).map(([source, timestamp]) => (
              <div key={source} className="flex items-center justify-between gap-3 border-b border-surface1 pb-2 text-xs">
                <dt className="capitalize text-subtext0">{source.replaceAll('_', ' ')}</dt>
                <dd className="tabular-nums text-text">{ts(timestamp)}</dd>
              </div>
            ))}
          </dl>
        </Panel>
      ) : null}

      <Panel title="Source caps and governance notes">
        <ul className="list-disc space-y-1.5 pl-4 text-xs text-subtext1 marker:text-overlay0">
          {data.source_caps.map((cap, i) => <li key={i}>{cap}</li>)}
        </ul>
      </Panel>

      <Panel
        title="Competition coverage matrix"
        actions={<span className="flex flex-wrap items-center gap-2">
          <Chip tone="positive">Complete</Chip><Chip tone="warning">Live partial</Chip><Chip>Missing</Chip>
        </span>}
        bodyClassName="p-0"
      >
        <DataTable minWidth={560} caption="Competition coverage matrix">
          <THead>
            <tr><Th>League</Th>{uniqueSeasons.map((year) => <Th key={year} align="center">{year}/{String(year + 1).slice(2)}</Th>)}</tr>
          </THead>
          <TBody>
            {uniqueCompetitions.map((comp) => (
              <tr key={comp}>
<Td><span className="flex items-center gap-2 font-medium"><CompetitionBadge code={comp} name={comp} size={18} />{comp}</span></Td>
                {uniqueSeasons.map((year) => {
                  const status = gridMatrix.get(`${comp}_${year}`) || 'missing';
                  return (
                    <Td key={year} align="center">
                      {status === 'complete' ? <Chip tone="positive">Complete</Chip>
                        : status === 'live_partial' ? <Chip tone="warning">Live</Chip>
                        : <span className="text-overlay0">—</span>}
                    </Td>
                  );
                })}
              </tr>
            ))}
          </TBody>
        </DataTable>
      </Panel>

      {data.null_coverage && Object.keys(data.null_coverage).length > 0 && (
        <Panel title="Critical metric missingness" description="Share of rows where each field is empty">
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
            {Object.entries(data.null_coverage).map(([col, rate]) => (
              <Stat key={col} inset label={<span className="font-mono">{col}</span>} value={`${(rate * 100).toFixed(2)}%`} />
            ))}
          </div>
        </Panel>
      )}

      {data.shot_coverage.length ? (
        <Panel title="Shot-field coverage" bodyClassName="p-0">
          <DataTable minWidth={480} caption="Shot-field coverage">
            <THead><tr><Th>Competition</Th><Th>Season</Th><Th align="right">Matches</Th><Th align="right">Complete</Th><Th align="right">Coverage</Th></tr></THead>
            <TBody>
              {data.shot_coverage.map((row) => (
                <tr key={`${row.competition}-${row.season}`}>
  <Td><span className="flex items-center gap-2 font-medium"><CompetitionBadge code={row.competition} name={row.competition} size={18} />{row.competition}</span></Td>
                  <Td className="text-subtext1">{row.season}/{String(row.season + 1).slice(-2)}</Td>
                  <Td align="right" className="text-subtext1">{row.matches}</Td>
                  <Td align="right" className="text-subtext1">{row.shot_matches}</Td>
                  <Td align="right" className="font-semibold">{row.coverage_pct.toFixed(1)}%</Td>
                </tr>
              ))}
            </TBody>
          </DataTable>
        </Panel>
      ) : null}

      {data.checksums && data.checksums.length > 0 && (
        <Panel title="Recent ingestion runs and checksums" bodyClassName="p-0"
          actions={<TableFilter label="Filter ingestion runs" placeholder="League or status…" value={runTable.query} onChange={runTable.setQuery} shown={runTable.rows.length} total={runTable.total} />}>
          <DataTable minWidth={720} caption="Ingestion runs">
            <THead><tr>
              <SortTh {...runTable.sortProps('league')}>League</SortTh>
              <SortTh {...runTable.sortProps('season')}>Season</SortTh>
              <SortTh align="right" {...runTable.sortProps('rows')}>Rows</SortTh>
              <SortTh {...runTable.sortProps('status')}>Status</SortTh>
              <Th>SHA-256</Th>
              <SortTh {...runTable.sortProps('fetched')}>Ingested</SortTh>
            </tr></THead>
            <TBody>
              {paginatedChecksums.map((chk, i) => (
                <tr key={i}>
                  <Td><span className="flex items-center gap-2 font-medium"><CompetitionBadge code={chk.league} name={chk.league || ''} size={18} />{chk.league}</span></Td>
                  <Td className="text-subtext1">{chk.season}</Td>
                  <Td align="right">{chk.row_count}</Td>
                  <Td><Chip tone={chk.status === 'success' || chk.status === 'cached' ? 'positive' : 'warning'}>{chk.status}</Chip></Td>
                  <Td className="max-w-[200px] truncate font-mono text-xs text-subtext0">{chk.sha256 || 'n/a'}</Td>
                  <Td className="text-subtext0">{chk.fetched_at?.slice(0, 16) || '–'}</Td>
                </tr>
              ))}
            </TBody>
          </DataTable>
          <div className="px-4 pb-3">{ChecksumsPagination}</div>
        </Panel>
      )}
    </div>
  );
}

export default function QualityPage() {
  return (
    <div className="space-y-5">
      <PageHeader icon={ShieldCheck} eyebrow="Trust and provenance" title="Data Quality & Observability" description="See coverage, freshness, source constraints and ingestion evidence before relying on an analysis." />

      <PipelineHealth />

      <Suspense fallback={<LoadingSkeleton lines={10} />}>
        <QualityContent />
      </Suspense>
    </div>
  );
}
