'use client';

import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import type { PlayerProfileResponse } from '@/lib/api/types';
import { Panel } from '@/components/ui/panel';
import { Chip } from '@/components/ui/chip';
import { Stat } from '@/components/ui/stat';
import { SectionHeading } from '@/components/ui/section-heading';
import { DataTable, TBody, THead, Td, Th } from '@/components/ui/data-table';
import { usePagination } from '@/components/ui/pagination';
import { FootballBadge, PlayerAvatar } from '@/lib/media-utils';
import { axisProps, gridProps, legendProps, SERIES, tooltipProps } from '@/lib/chart-theme';

export function formatCurrency(eur: number | null | undefined): string {
  if (!eur) return 'N/A';
  if (eur >= 1_000_000_000) return `€${(eur / 1_000_000_000).toFixed(1)}B`;
  if (eur >= 1_000_000) return `€${(eur / 1_000_000).toFixed(1)}M`;
  if (eur >= 1_000) return `€${(eur / 1_000).toFixed(0)}k`;
  return `€${eur.toLocaleString()}`;
}

interface SeasonTotal { season: string; appearances: number; goals: number; assists: number; minutes: number }

export function PlayerProfile({
  profile,
  seasonTotals,
}: {
  profile: PlayerProfileResponse;
  seasonTotals: SeasonTotal[];
}) {
  const totals = seasonTotals.reduce((acc, row) => ({
    appearances: acc.appearances + row.appearances,
    goals: acc.goals + row.goals,
    assists: acc.assists + row.assists,
    minutes: acc.minutes + row.minutes,
  }), { appearances: 0, goals: 0, assists: 0, minutes: 0 });
  const bio: [string, string][] = [
    ['Nationality', profile.nationality || 'N/A'],
    ['Date of birth', profile.date_born || 'N/A'],
    ['Height', profile.height_cm ? `${profile.height_cm} cm` : 'N/A'],
    ['Preferred foot', profile.foot || 'N/A'],
  ];

  return (
    <Panel bodyClassName="space-y-5">
      <div className="flex flex-col justify-between gap-4 border-b border-surface1 pb-4 sm:flex-row sm:items-center">
        <div className="flex items-center gap-3">
          <PlayerAvatar image_url={profile.image_url} name={profile.name} size={56} className="rounded-xl" />
          <div className="min-w-0">
            <h2 className="truncate text-lg font-semibold text-text">{profile.name}</h2>
            <p className="mt-0.5 flex items-center gap-2 text-[13px] text-subtext1">
              <FootballBadge url={profile.team.badge_url} name={profile.team.name} size={16} />
              {profile.team.name}
              {profile.position && <Chip>{profile.position}</Chip>}
            </p>
          </div>
        </div>
        <div className="sm:text-right">
          <p className="text-xs text-subtext0">Market value</p>
          <p className="text-2xl font-semibold tabular-nums text-text">{formatCurrency(profile.market_value_eur)}</p>
        </div>
      </div>

      <dl className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        {bio.map(([label, val]) => (
          <div key={label}>
            <dt className="text-xs text-subtext0">{label}</dt>
            <dd className="text-[13px] font-medium capitalize text-text">{val}</dd>
          </div>
        ))}
      </dl>

      {seasonTotals.length ? (
        <div className="space-y-3">
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
            <Stat inset label="Appearances" value={totals.appearances} />
            <Stat inset label="Goals" value={totals.goals} />
            <Stat inset label="Assists" value={totals.assists} />
            <Stat inset label="Minutes" value={totals.minutes.toLocaleString()} />
          </div>
          <div className="h-56">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={seasonTotals} margin={{ top: 4, right: 4, left: -20, bottom: 0 }}>
                <CartesianGrid {...gridProps} />
                <XAxis dataKey="season" {...axisProps} />
                <YAxis {...axisProps} allowDecimals={false} />
                <Tooltip {...tooltipProps} />
                <Legend {...legendProps} />
                <Bar dataKey="goals" name="Goals" fill={SERIES[0]} radius={[3, 3, 0, 0]} maxBarSize={28} />
                <Bar dataKey="assists" name="Assists" fill={SERIES[2]} radius={[3, 3, 0, 0]} maxBarSize={28} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      ) : null}

      <div className="space-y-2">
        <SectionHeading level={3}>Season statistics</SectionHeading>
        <PlayerStatsTable stats={profile.stats} />
      </div>
    </Panel>
  );
}

function PlayerStatsTable({ stats }: { stats: PlayerProfileResponse['stats'] }) {
  const { paginatedItems, paginationControls } = usePagination(stats, 10);
  if (stats.length === 0) {
    return <p className="py-4 text-xs text-subtext0">No historical competition stats recorded for this profile.</p>;
  }
  return (
    <div className="space-y-2">
      <div className="overflow-hidden rounded-lg border border-surface1">
        <DataTable minWidth={520} caption="Season statistics">
          <THead>
            <tr><Th>Season</Th><Th>Competition</Th><Th align="right">Apps</Th><Th align="right">Goals</Th><Th align="right">Assists</Th><Th align="right">Mins</Th><Th align="right">Yel</Th><Th align="right">Red</Th></tr>
          </THead>
          <TBody>
            {paginatedItems.map((st, i) => (
              <tr key={i}>
                <Td className="font-medium">{st.season}</Td>
                <Td className="capitalize text-subtext1">{st.competition || 'domestic'}</Td>
                <Td align="right">{st.appearances ?? '–'}</Td>
                <Td align="right" className="font-semibold">{st.goals ?? 0}</Td>
                <Td align="right">{st.assists ?? 0}</Td>
                <Td align="right" className="text-subtext0">{st.minutes_played?.toLocaleString() ?? '–'}</Td>
                <Td align="right" className="text-subtext0">{st.yellow_cards ?? 0}</Td>
                <Td align="right" className="text-subtext0">{st.red_cards ?? 0}</Td>
              </tr>
            ))}
          </TBody>
        </DataTable>
      </div>
      {paginationControls}
    </div>
  );
}
