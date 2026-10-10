import type { ReactNode } from 'react';
import type { RankingRow } from '@/lib/api/types';
import { Panel } from '@/components/ui/panel';
import { FormChip } from '@/components/ui/chip';
import { DataTable, SortTh, TBody, THead, Td, Th } from '@/components/ui/data-table';
import { CompetitionBadge } from '@/lib/media-utils';
import { seasonLabel } from '../_lib';

type SortKey = 'season' | 'competition' | 'played' | 'wins' | 'draws' | 'losses' | 'goalsFor' | 'goalsAgainst' | 'goalDifference' | 'points' | 'ppg';

export function SeasonTable({
  seasons,
  pagination,
  sortProps,
}: {
  seasons: RankingRow[];
  pagination: ReactNode;
  sortProps: (key: SortKey) => { dir?: 'asc' | 'desc'; onSort: () => void };
}) {
  return (
    <Panel title="Season history" bodyClassName="p-0">
      <DataTable minWidth={760} caption="Season history">
        <THead>
          <tr>
            <SortTh {...sortProps('season')}>Season</SortTh>
            <SortTh {...sortProps('competition')}>League</SortTh>
            <SortTh align="right" {...sortProps('played')}>P</SortTh>
            <SortTh align="right" {...sortProps('wins')}>W</SortTh>
            <SortTh align="right" {...sortProps('draws')}>D</SortTh>
            <SortTh align="right" {...sortProps('losses')}>L</SortTh>
            <SortTh align="right" {...sortProps('goalsFor')}>GF</SortTh>
            <SortTh align="right" {...sortProps('goalsAgainst')}>GA</SortTh>
            <SortTh align="right" {...sortProps('goalDifference')}>GD</SortTh>
            <SortTh align="right" {...sortProps('points')}>Pts</SortTh>
            <SortTh align="right" {...sortProps('ppg')}>PPG</SortTh>
            <Th align="center">Form</Th>
          </tr>
        </THead>
        <TBody>
          {seasons.map((s) => (
            <tr key={`${s.competition}_${s.season}`}>
              <Td className="font-medium">{seasonLabel(s.season)}</Td>
              <Td><span className="flex items-center gap-2"><CompetitionBadge code={s.competition} name={s.competition} size={18} />{s.competition}</span></Td>
              <Td align="right" className="text-subtext1">{s.played}</Td>
              <Td align="right" className="text-subtext1">{s.wins}</Td>
              <Td align="right" className="text-subtext1">{s.draws}</Td>
              <Td align="right" className="text-subtext1">{s.losses}</Td>
              <Td align="right" className="text-subtext1">{s.goals_for}</Td>
              <Td align="right" className="text-subtext1">{s.goals_against}</Td>
              <Td align="right" className={s.goal_difference > 0 ? 'text-positive' : s.goal_difference < 0 ? 'text-negative' : 'text-subtext0'}>
                {s.goal_difference > 0 ? `+${s.goal_difference}` : s.goal_difference}
              </Td>
              <Td align="right" className="font-semibold">{s.points}</Td>
              <Td align="right" className="text-subtext0">{s.points_per_game.toFixed(2)}</Td>
              <Td align="center">
                <span className="inline-flex gap-1">
                  {(s.form || '').split(' ').filter(Boolean).map((result, index) => <FormChip key={index} result={result} />)}
                </span>
              </Td>
            </tr>
          ))}
        </TBody>
      </DataTable>
      <div className="px-4 pb-3">{pagination}</div>
    </Panel>
  );
}
