import { Button } from '@heroui/react';
import { ChevronLeft, ChevronRight, UsersRound } from 'lucide-react';
import type { PlayerSummary } from '@/lib/api/types';
import { Chip } from '@/components/ui/chip';
import { EmptyState, LoadingSkeleton } from '@/components/ui/loading';
import { PlayerAvatar } from '@/lib/media-utils';
import type { ComparisonPlayer } from './player-comparison';

export function PlayerList({
  players,
  total,
  query,
  isLoading,
  selectedId,
  onSelect,
  comparison,
  onToggleComparison,
  canGoBack,
  canGoForward,
  onPrev,
  onNext,
}: {
  players: PlayerSummary[];
  total: number;
  query: string;
  isLoading: boolean;
  selectedId: string | null;
  onSelect: (id: string) => void;
  comparison: [ComparisonPlayer | null, ComparisonPlayer | null];
  onToggleComparison: (player: ComparisonPlayer) => void;
  canGoBack: boolean;
  canGoForward: boolean;
  onPrev: () => void;
  onNext: () => void;
}) {
  return (
    <div className="overflow-hidden rounded-xl border border-surface1 bg-surface0">
      <div className="flex items-center justify-between gap-2 border-b border-surface1 px-4 py-2.5 text-xs text-subtext0">
        <span className="tabular-nums">{total.toLocaleString()} players</span>
        {query && <Chip tone="accent" className="truncate">Matching “{query}”</Chip>}
      </div>

      {isLoading && players.length === 0 ? (
        <div className="p-4"><LoadingSkeleton lines={6} /></div>
      ) : players.length === 0 ? (
        <EmptyState icon={UsersRound} message="No players found." suggestion="Try another spelling or clear search." />
      ) : (
        <ul className="max-h-[640px] overflow-y-auto">
          {players.map((p) => {
            const selected = selectedId === p.player_id;
            const slot = comparison.findIndex((player) => player?.id === p.player_id);
            return (
              <li key={p.player_id} className={`relative flex items-center border-b border-surface1 last:border-b-0 ${selected ? 'bg-surface1/50' : 'hover:bg-surface1/30'}`}>
                {selected ? <span className="absolute inset-y-2 left-0 w-0.5 rounded-r bg-accent" aria-hidden="true" /> : null}
                <button type="button" aria-label={`View profile for ${p.name}`} aria-pressed={selected} onClick={() => onSelect(p.player_id)}
                  className="flex min-w-0 flex-1 items-center gap-3 px-4 py-2.5 text-left">
                  <PlayerAvatar image_url={p.image_url} name={p.name} size={32} />
                  <span className="min-w-0">
                    <span className={`block truncate text-[13px] font-medium ${selected ? 'text-accent' : 'text-text'}`}>{p.name}</span>
                    <span className="block truncate text-xs text-subtext0">{p.team.name}{p.position ? ` · ${p.position}` : ''}</span>
                  </span>
                </button>
                <button type="button"
                  aria-label={`${slot >= 0 ? 'Remove' : 'Add'} ${p.name} ${slot >= 0 ? 'from' : 'to'} comparison`}
                  aria-pressed={slot >= 0}
                  onClick={() => onToggleComparison({ id: p.player_id, name: p.name })}
                  className={`mr-3 h-7 shrink-0 rounded-md border px-2 text-xs font-medium transition-colors ${slot >= 0 ? 'border-accent text-accent' : 'border-surface1 text-subtext1 hover:bg-surface1'}`}>
                  {slot >= 0 ? `Player ${slot + 1}` : 'Compare'}
                </button>
              </li>
            );
          })}
        </ul>
      )}

      <div className="flex items-center justify-between border-t border-surface1 px-3 py-2 text-xs text-subtext0">
        <Button size="sm" variant="ghost" isDisabled={!canGoBack} onPress={onPrev}>
          <ChevronLeft className="size-3.5" aria-hidden="true" /> Prev
        </Button>
        <span className="tabular-nums">{players.length} shown</span>
        <Button size="sm" variant="ghost" isDisabled={!canGoForward} onPress={onNext}>
          Next <ChevronRight className="size-3.5" aria-hidden="true" />
        </Button>
      </div>
    </div>
  );
}
