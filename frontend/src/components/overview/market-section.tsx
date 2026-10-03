'use client';

import { useEffect, useMemo, useRef, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import Link from 'next/link';
import { Button, Card, Chip } from '@heroui/react';
import { ArrowRightLeft, Calendar, ChevronLeft, ChevronRight, Shield, Sparkles } from 'lucide-react';
import { api } from '@/lib/api/client';
import { queryKeys } from '@/lib/api/query-keys';
import { LoadingSkeleton } from '@/components/ui/loading';
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

  return (
    <>
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
    </>
  );
}
