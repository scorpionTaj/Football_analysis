import type { PlayerProfileResponse, PlayerStat } from '@/lib/api/types';
import { Panel } from '@/components/ui/panel';
import { Select } from '@/components/ui/select';
import { DataTable, TBody, THead, Td, Th } from '@/components/ui/data-table';
import { ErrorMessage, LoadingSkeleton } from '@/components/ui/loading';

export interface ComparisonPlayer { id: string; name: string }
export interface ComparisonOption { key: string; season: string; competition: string | null }

const value = (v: number | null | undefined) => (v == null ? '—' : v.toLocaleString());
const per90 = (v: number | null | undefined, minutes: number | null | undefined) =>
  v == null || minutes == null || minutes <= 0 ? '—' : ((v * 90) / minutes).toFixed(2);

export function PlayerComparison({
  players,
  onRemove,
  profiles,
  isLoading,
  error,
  retry,
  options,
  selectedKey,
  onSelectKey,
  stats,
}: {
  players: [ComparisonPlayer | null, ComparisonPlayer | null];
  onRemove: (player: ComparisonPlayer) => void;
  profiles: [PlayerProfileResponse | undefined, PlayerProfileResponse | undefined];
  isLoading: boolean;
  error: Error | null;
  retry: () => void;
  options: ComparisonOption[];
  selectedKey: string;
  onSelectKey: (key: string) => void;
  stats: (PlayerStat | undefined)[];
}) {
  const [first, second] = profiles;
  const rows: [string, string, string][] = [
    ['Appearances', value(stats[0]?.appearances), value(stats[1]?.appearances)],
    ['Goals', value(stats[0]?.goals), value(stats[1]?.goals)],
    ['Assists', value(stats[0]?.assists), value(stats[1]?.assists)],
    ['Minutes', value(stats[0]?.minutes_played), value(stats[1]?.minutes_played)],
    ['Goals / 90', per90(stats[0]?.goals, stats[0]?.minutes_played), per90(stats[1]?.goals, stats[1]?.minutes_played)],
    ['Assists / 90', per90(stats[0]?.assists, stats[0]?.minutes_played), per90(stats[1]?.assists, stats[1]?.minutes_played)],
  ];

  return (
    <section aria-label="Player comparison">
      <Panel
        as="div"
        title="Compare players"
        description="Transfermarkt Open Dataset · 2025/26 snapshot, through July 2026. These are historical records, not current 2026/27 squads. Choosing a third player replaces Player 2."
        bodyClassName="space-y-4"
      >
        <div className="grid gap-3 sm:grid-cols-2">
          {players.map((player, index) => (
            <div key={index} className="flex items-center justify-between gap-3 rounded-lg border border-surface1 bg-mantle px-3 py-2.5">
              <div className="min-w-0">
                <p className="text-xs text-subtext0">Player {index + 1}</p>
                <p className="truncate text-[13px] font-medium text-text">{player?.name || 'Choose from the list below'}</p>
              </div>
              {player && (
                <button type="button" onClick={() => onRemove(player)} aria-label={`Remove ${player.name} from comparison`}
                  className="shrink-0 rounded-md px-2 py-1 text-xs font-medium text-accent hover:bg-surface1">
                  Remove
                </button>
              )}
            </div>
          ))}
        </div>
        {players[0] && players[1] && (
          isLoading ? <LoadingSkeleton lines={4} /> :
          error ? <ErrorMessage title="Failed to load comparison" detail={error.message || 'Try again.'} retry={retry} /> :
          first && second ? (
            options.length ? (
              <div className="space-y-3">
                <Select label="Season and competition" value={selectedKey} onChange={onSelectKey} className="sm:max-w-sm"
                  options={options.map((option) => ({ value: option.key, label: `${option.season} · ${option.competition || 'Unspecified competition'}` }))} />
                <div className="overflow-hidden rounded-lg border border-surface1">
                  <DataTable minWidth={280} caption={`Historical season statistics for ${first.name} and ${second.name}`}>
                    <THead><tr><Th>Metric</Th><Th align="right">Player 1</Th><Th align="right">Player 2</Th></tr></THead>
                    <TBody>
                      {rows.map(([label, a, b]) => (
                        <tr key={label}>
                          <th scope="row" className="h-9 px-3 text-left font-medium text-text">{label}</th>
                          <Td align="right">{a}</Td>
                          <Td align="right">{b}</Td>
                        </tr>
                      ))}
                    </TBody>
                  </DataTable>
                </div>
                <p className="text-xs text-subtext0">— means unavailable. Per-90 figures require recorded minutes above zero.</p>
              </div>
            ) : <p className="text-sm text-subtext0">No historical season statistics are available for these players.</p>
          ) : null
        )}
      </Panel>
    </section>
  );
}
