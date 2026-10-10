import type { ReactNode } from 'react';
import { CalendarDays } from 'lucide-react';
import type { Match } from '@/lib/api/types';
import { Panel } from '@/components/ui/panel';
import { Chip, FormChip } from '@/components/ui/chip';
import { EmptyState, ErrorMessage, LoadingSkeleton } from '@/components/ui/loading';
import { FootballBadge } from '@/lib/media-utils';
import { fromClubSide } from '../_lib';

export function MatchLog({
  matches,
  isClubHome,
  isLoading,
  error,
  retry,
  pagination,
}: {
  matches: Match[];
  isClubHome: (match: Match) => boolean;
  isLoading: boolean;
  error: Error | null;
  retry: () => void;
  pagination: ReactNode;
}) {
  return (
    <Panel title="Recent fixtures" bodyClassName="p-0">
      {isLoading ? (
        <div className="p-4"><LoadingSkeleton lines={4} /></div>
      ) : error ? (
        <div className="p-4"><ErrorMessage title="Fixtures unavailable" detail={error.message} retry={retry} /></div>
      ) : matches.length === 0 ? (
        <EmptyState icon={CalendarDays} message="No recent fixtures recorded for this club." />
      ) : (
        <>
          <ul>
            {matches.map((m, idx) => {
              const home = isClubHome(m);
              const opponent = home ? m.away : m.home;
              const { result } = fromClubSide(m, home);
              return (
                <li key={`${m.match_date}_${idx}`} className="flex items-center justify-between gap-3 border-b border-surface1 px-4 py-2 text-[13px] last:border-b-0">
                  <span className="flex min-w-0 items-center gap-3">
                    <span className="w-20 shrink-0 text-xs tabular-nums text-subtext0">{m.match_date}</span>
                    <Chip>{home ? 'Home' : 'Away'}</Chip>
                    <FootballBadge name={opponent.name} url={opponent.badge_url} size={18} />
                    <span className="truncate text-text">{opponent.name}</span>
                  </span>
                  <span className="flex shrink-0 items-center gap-3">
                    <span className="font-semibold tabular-nums text-text">{m.home_goals ?? '–'} : {m.away_goals ?? '–'}</span>
                    {result ? <FormChip result={result} /> : null}
                  </span>
                </li>
              );
            })}
          </ul>
          <div className="px-4 pb-3">{pagination}</div>
        </>
      )}
    </Panel>
  );
}
