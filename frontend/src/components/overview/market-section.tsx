'use client';

import { useEffect, useMemo, useRef, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import Link from 'next/link';
import { Button } from '@heroui/react';
import { ArrowRight, ArrowRightLeft, ChevronLeft, ChevronRight } from 'lucide-react';
import { api } from '@/lib/api/client';
import { queryKeys } from '@/lib/api/query-keys';
import { EmptyState, LoadingSkeleton } from '@/components/ui/loading';
import { Panel } from '@/components/ui/panel';
import { Select } from '@/components/ui/select';
import { DataTable, TBody, THead, Td, Th } from '@/components/ui/data-table';
import { FootballBadge, PlayerAvatar } from '@/lib/media-utils';

export const BIG_5_COMPS = [
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

/**
 * Transfer market and star players. Owns its filters and pagination and only fetches once
 * scrolled near, so paging transfers never re-renders the rest of the overview.
 */
export function MarketSection() {
  const [marketVisible, setMarketVisible] = useState(false);
  const marketRef = useRef<HTMLDivElement>(null);
  const [transferComp, setTransferComp] = useState<string>('all');
  const [transferSeason, setTransferSeason] = useState<number | 'all'>('all');
  const [transferPage, setTransferPage] = useState<number>(1);
  const transferPageSize = 10;

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
  }, [marketVisible]);

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

  const money = (value: number, digits = 1) => `€${(value / 1e6).toFixed(digits)}M`;
  return (
    <>
      <div ref={marketRef}>
        <Panel
          title="Transfer market"
          description="Top recorded transfers across the five biggest leagues, including 2026/27 when the source has it."
          actions={<>
            <Select hideLabel label="Transfer competition" value={transferComp}
              onChange={(value) => { setTransferComp(value); setTransferPage(1); }}
              options={BIG_5_COMPS.map((c) => ({ value: c.code, label: c.name }))} className="w-44" />
            <Select hideLabel label="Transfer season" value={String(transferSeason)}
              onChange={(value) => { setTransferSeason(value === 'all' ? 'all' : Number(value)); setTransferPage(1); }}
              options={RECENT_TRANSFER_SEASONS.map((season) => ({ value: String(season.value), label: season.label }))} className="w-44" />
          </>}
          bodyClassName="p-0"
        >
          {!marketVisible || isTransfersLoading ? (
            <div className="p-4"><LoadingSkeleton lines={5} /></div>
          ) : paginatedTransfers.length > 0 ? (
            <>
              <DataTable minWidth={760}>
                <THead>
                  <tr>
                    <Th>Player</Th>
                    <Th>From</Th>
                    <Th>To</Th>
                    <Th align="right">Fee</Th>
                    <Th align="right">Market value</Th>
                    <Th align="right">Season</Th>
                  </tr>
                </THead>
                <TBody>
                  {paginatedTransfers.map((t) => (
                    <tr key={t.transfer_id}>
                      <Td>
                        <span className="flex items-center gap-2.5">
                          <PlayerAvatar image_url={t.image_url} name={t.player_name} size={28} />
                          <span className="font-medium">{t.player_name}</span>
                        </span>
                      </Td>
                      <Td>
                        <span className="flex items-center gap-2 text-subtext1">
                          <FootballBadge url={t.from_club.badge_url} name={t.from_club.name} size={18} />
                          <span className="max-w-[160px] truncate">{t.from_club.name}</span>
                        </span>
                      </Td>
                      <Td>
                        <span className="flex items-center gap-2">
                          <ArrowRight className="size-3.5 shrink-0 text-overlay0" aria-label="to" />
                          <FootballBadge url={t.to_club.badge_url} name={t.to_club.name} size={18} />
                          <span className="max-w-[160px] truncate">{t.to_club.name}</span>
                        </span>
                      </Td>
                      <Td align="right" className="font-medium">
                        {t.transfer_fee && t.transfer_fee > 0 ? money(t.transfer_fee) : <span className="font-normal text-subtext0">Free / loan</span>}
                      </Td>
                      <Td align="right" className="text-subtext1">
                        {t.market_value_eur && t.market_value_eur > 0 ? money(t.market_value_eur, 0) : '—'}
                      </Td>
                      <Td align="right" className="text-subtext0">
                        {t.transfer_season}{t.transfer_date ? <span className="ml-1.5 hidden xl:inline">{t.transfer_date}</span> : null}
                      </Td>
                    </tr>
                  ))}
                </TBody>
              </DataTable>
              <div className="flex flex-col gap-3 border-t border-surface1 px-4 py-3 text-xs text-subtext0 sm:flex-row sm:items-center sm:justify-between">
                <span className="tabular-nums">
                  Showing deals {(transferPage - 1) * transferPageSize + 1} to{' '}
                  {Math.min(transferPage * transferPageSize, allTransfers.length)} of {allTransfers.length} loaded
                </span>
                <div className="flex items-center gap-2">
                  <Button size="sm" variant="outline" isDisabled={transferPage <= 1} onPress={() => setTransferPage((p) => Math.max(1, p - 1))}>
                    <ChevronLeft className="size-3.5" aria-hidden="true" /> Previous
                  </Button>
                  <span className="tabular-nums text-text">Page {transferPage} of {totalTransferPages}</span>
                  <Button size="sm" variant="outline" isDisabled={transferPage >= totalTransferPages} onPress={() => setTransferPage((p) => Math.min(totalTransferPages, p + 1))}>
                    Next <ChevronRight className="size-3.5" aria-hidden="true" />
                  </Button>
                </div>
              </div>
            </>
          ) : (
            <EmptyState
              icon={ArrowRightLeft}
              message="No transfers for these filters"
              suggestion={transferSeason === 2026
                ? 'The current Transfermarkt Open Dataset snapshot ends in July 2026 and has no 2026/27 deals yet.'
                : 'Try another season or competition.'}
            />
          )}
        </Panel>
      </div>

      {starPlayersData?.players && starPlayersData.players.length > 0 && (
        <Panel
          title="Most valuable players"
          description="Highest market valuations in the Transfermarkt snapshot"
          actions={<Link href="/players" className="inline-flex items-center gap-1 text-xs font-medium text-accent hover:underline">
            All players <ChevronRight className="size-3.5" aria-hidden="true" />
          </Link>}
        >
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4 lg:grid-cols-8">
            {starPlayersData.players.map((p) => (
              <Link
                key={p.player_id}
                href={`/players?q=${encodeURIComponent(p.name)}`}
                className="group flex flex-col items-center rounded-lg border border-surface1 p-3 text-center transition-colors hover:border-surface2 hover:bg-surface1/40"
              >
                <span className="relative mb-2">
                  <PlayerAvatar image_url={p.image_url} name={p.name} size={52} />
                  <span className="absolute -bottom-1 -right-1">
                    <FootballBadge url={p.team.badge_url} name={p.team.name} size={18} />
                  </span>
                </span>
                <span className="w-full truncate text-xs font-medium text-text group-hover:text-accent">{p.name}</span>
                <span className="w-full truncate text-xs text-subtext0">{p.position || 'Player'}</span>
                {p.market_value_eur ? <span className="mt-1 text-xs font-semibold tabular-nums text-text">{money(p.market_value_eur, 0)}</span> : null}
              </Link>
            ))}
          </div>
        </Panel>
      )}
    </>
  );
}
