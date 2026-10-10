import type { ReactNode } from 'react';
import type { RankingRow } from '@/lib/api/types';
import { Panel } from '@/components/ui/panel';
import { Chip, FormChip } from '@/components/ui/chip';
import { DataTable, TBody, THead, Td, Th } from '@/components/ui/data-table';
import { seasonLabel } from '../_lib';

export function SeasonTable({ seasons, pagination }: { seasons: RankingRow[]; pagination: ReactNode }) {
  return (
    <Panel title="Season history" bodyClassName="p-0">
      <DataTable minWidth={760} caption="Season history">
        <THead>
          <tr>
            <Th>Season</Th>
            <Th>League</Th>
            <Th align="right">P</Th>
            <Th align="right">W</Th>
            <Th align="right">D</Th>
            <Th align="right">L</Th>
            <Th align="right">GF</Th>
            <Th align="right">GA</Th>
            <Th align="right">GD</Th>
            <Th align="right" className="text-text">Pts</Th>
            <Th align="right">PPG</Th>
            <Th align="center">Form</Th>
          </tr>
        </THead>
        <TBody>
          {seasons.map((s) => (
            <tr key={`${s.competition}_${s.season}`}>
              <Td className="font-medium">{seasonLabel(s.season)}</Td>
              <Td><Chip>{s.competition}</Chip></Td>
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
