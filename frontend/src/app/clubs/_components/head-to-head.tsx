import type { ReactNode } from 'react';
import { Swords } from 'lucide-react';
import type { Match } from '@/lib/api/types';
import { Panel } from '@/components/ui/panel';
import { Chip } from '@/components/ui/chip';
import { EmptyState, ErrorMessage, LoadingSkeleton } from '@/components/ui/loading';
import { FootballBadge } from '@/lib/media-utils';
import { fromClubSide, type ClubTotals } from '../_lib';

export interface H2HStats { clashes: number; clubAWins: number; clubBWins: number; draws: number; clubAGoals: number; clubBGoals: number }
interface Side { name: string; badge?: string | null; totals: ClubTotals }

/** Club A uses the home outcome colour, club B the away colour, everywhere in this view. */
const A = 'var(--outcome-home)';
const B = 'var(--outcome-away)';

export function HeadToHead({
  a,
  b,
  stats,
  matches,
  isClubHome,
  isLoading,
  error,
  retry,
  pagination,
}: {
  a: Side;
  b: Side;
  stats: H2HStats;
  matches: Match[];
  isClubHome: (match: Match) => boolean;
  isLoading: boolean;
  error: Error | null;
  retry: () => void;
  pagination: ReactNode;
}) {
  const goals = stats.clubAGoals + stats.clubBGoals;
  const share = goals > 0 ? (stats.clubAGoals / goals) * 100 : 50;
  const comparisons: [string, string, string][] = [
    ['Points per game', a.totals.ppg, b.totals.ppg],
    ['Win rate', `${a.totals.winRate}%`, `${b.totals.winRate}%`],
    ['Goals / match', a.totals.gfPerMatch, b.totals.gfPerMatch],
    ['Clean sheets', `${a.totals.cleanSheetRate}%`, `${b.totals.cleanSheetRate}%`],
  ];

  return (
    <div className="space-y-4">
      <Panel>
        <div className="grid grid-cols-[minmax(0,1fr)_auto_minmax(0,1fr)] items-center gap-4">
          <ClubSide side={a} wins={stats.clubAWins} color={A} />
          <div className="rounded-lg bg-mantle px-4 py-2 text-center">
            <p className="text-xs text-subtext0">Meetings</p>
            <p className="text-2xl font-semibold tabular-nums text-text">{stats.clashes}</p>
            <p className="text-xs tabular-nums text-subtext0">{stats.draws} draws</p>
          </div>
          <ClubSide side={b} wins={stats.clubBWins} color={B} alignEnd />
        </div>
        <div className="mt-5 border-t border-surface1 pt-4">
          <div className="mb-1.5 flex justify-between text-xs tabular-nums text-subtext0">
            <span>{stats.clubAGoals} goals</span>
            <span>Head-to-head goals</span>
            <span>{stats.clubBGoals} goals</span>
          </div>
          <div className="flex h-1.5 gap-px overflow-hidden rounded-full bg-surface1">
            <div style={{ width: `${share}%`, background: A }} />
            <div style={{ width: `${100 - share}%`, background: B }} />
          </div>
        </div>
      </Panel>

      <Panel title="All-seasons comparison">
        <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
          {comparisons.map(([label, left, right]) => (
            <div key={label} className="rounded-lg border border-surface1 bg-mantle px-3 py-2.5">
              <p className="text-xs text-subtext0">{label}</p>
              <p className="mt-1 flex items-baseline justify-between text-sm font-semibold tabular-nums">
                <span className="text-text">{left}</span>
                <span className="text-xs font-normal text-overlay0">vs</span>
                <span className="text-text">{right}</span>
              </p>
            </div>
          ))}
        </div>
      </Panel>

      <Panel title={`Direct meetings (${matches.length})`} bodyClassName="p-0">
        {isLoading ? (
          <div className="p-4"><LoadingSkeleton lines={4} /></div>
        ) : error ? (
          <div className="p-4"><ErrorMessage title="Head-to-head unavailable" detail={error.message} retry={retry} /></div>
        ) : matches.length === 0 ? (
          <EmptyState
            icon={Swords}
            message={`No direct matches found between ${a.name} and ${b.name} in covered fixtures.`}
            suggestion="Select any two covered clubs to search direct meetings across leagues and cups."
          />
        ) : (
          <>
            <ul>
              {matches.map((m, idx) => {
                const { result } = fromClubSide(m, isClubHome(m));
                const verdict = result === 'W' ? `${a.name} win` : result === 'L' ? `${b.name} win` : result === 'D' ? 'Draw' : null;
                return (
                  <li key={`${m.match_date}_${idx}`} className="flex flex-col gap-2 border-b border-surface1 px-4 py-2.5 text-[13px] last:border-b-0 sm:flex-row sm:items-center sm:justify-between">
                    <span className="flex min-w-0 flex-wrap items-center gap-2">
                      <span className="w-20 shrink-0 text-xs tabular-nums text-subtext0">{m.match_date}</span>
                      <Chip>{m.competition}</Chip>
                      <span className="flex min-w-0 items-center gap-1.5 text-text">
                        <FootballBadge name={m.home.name} url={m.home.badge_url} size={18} />
                        <span className="truncate">{m.home.name}</span>
                        <span className="text-overlay0">v</span>
                        <span className="truncate">{m.away.name}</span>
                        <FootballBadge name={m.away.name} url={m.away.badge_url} size={18} />
                      </span>
                    </span>
                    <span className="flex shrink-0 items-center gap-3 self-end sm:self-auto">
                      <span className="font-semibold tabular-nums text-text">{m.home_goals ?? '–'} : {m.away_goals ?? '–'}</span>
                      {verdict ? <Chip tone={result === 'D' ? 'neutral' : 'accent'}>{verdict}</Chip> : null}
                    </span>
                  </li>
                );
              })}
            </ul>
            <div className="px-4 pb-3">{pagination}</div>
          </>
        )}
      </Panel>
    </div>
  );
}

function ClubSide({ side, wins, color, alignEnd = false }: { side: Side; wins: number; color: string; alignEnd?: boolean }) {
  return (
    <div className={`flex min-w-0 items-center gap-3 ${alignEnd ? 'flex-row-reverse text-right' : ''}`}>
      <FootballBadge name={side.name} url={side.badge} size={40} />
      <div className="min-w-0">
        <h3 className="truncate text-sm font-semibold text-text">{side.name}</h3>
        <p className="text-lg font-semibold tabular-nums text-text">
          <span className="mr-1.5 inline-block size-2 rounded-full align-middle" style={{ background: color }} aria-hidden="true" />
          {wins} wins
        </p>
      </div>
    </div>
  );
}
