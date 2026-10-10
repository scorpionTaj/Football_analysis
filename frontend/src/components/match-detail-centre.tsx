'use client';

import { Button, Card } from '@heroui/react';
import { useMemo, useState } from 'react';
import {
  ArrowLeft,
  CalendarDays,
  CircleAlert,
  MapPin,
  Shirt,
  Timer,
  UserRound,
  UsersRound,
} from 'lucide-react';
import type { EventLineupItem, MatchCentreDetailResponse } from '@/lib/api/types';
import { FootballBadge, PlayerAvatar } from '@/lib/media-utils';
import { SourceBadge } from '@/components/ui/source-badge';

type Side = 'home' | 'away';

function timelineMark(eventType: string | null) {
  const event = (eventType || '').toLowerCase();
  if (event.includes('missed')) return { mark: '✕', tone: 'border-red/35 bg-red/10 text-red' };
  if (event.includes('red') || event.includes('second yellow')) return { mark: '■', tone: 'border-red/35 bg-red/10 text-red' };
  if (event.includes('yellow')) return { mark: '■', tone: 'border-yellow/35 bg-yellow/10 text-yellow' };
  if (event.includes('substitution')) return { mark: '↔', tone: 'border-teal/35 bg-teal/10 text-teal' };
  if (event.includes('goal')) return { mark: '⚽', tone: 'border-green/35 bg-green/10 text-green' };
  return { mark: '•', tone: 'border-surface2 bg-mantle text-subtext1' };
}

function roleBand(position: string | null): number {
  const role = (position || '').toLocaleLowerCase();
  if (role.includes('goal')) return 88;
  if (role.includes('defensive')) return 58;
  if (role.includes('back') || role.includes('defen')) return 70;
  if (role.includes('mid')) return role.includes('attack') ? 34 : 48;
  if (role.includes('wing')) return 28;
  if (role.includes('forward') || role.includes('attack') || role.includes('striker')) return 17;
  return 45;
}

function positionedPlayers(players: EventLineupItem[]) {
  const bands = new Map<number, EventLineupItem[]>();
  for (const player of players) {
    const band = roleBand(player.position);
    bands.set(band, [...(bands.get(band) || []), player]);
  }
  return Array.from(bands.entries()).flatMap(([top, rows]) => rows.map((player, index) => ({
    player,
    top,
    left: ((index + 1) * 100) / (rows.length + 1),
  })));
}

function formationDots(formation: string | null) {
  const lines = (formation || '').match(/\d+/g)?.map(Number).filter((value) => value > 0 && value <= 6) || [];
  if (!lines.length) return [];
  const rows = [1, ...lines];
  return rows.flatMap((count, row) => Array.from({ length: count }, (_, index) => ({
    key: `${row}-${index}`,
    top: 88 - (row * 70) / Math.max(rows.length - 1, 1),
    left: ((index + 1) * 100) / (count + 1),
  })));
}

function Pitch({ detail, side }: { detail: MatchCentreDetailResponse; side: Side }) {
  const isHome = side === 'home';
  const team = isHome ? detail.match.home : detail.match.away;
  const formation = isHome ? detail.home_formation : detail.away_formation;
  const coach = isHome ? detail.home_coach : detail.away_coach;
  const starters = detail.lineups.filter((player) => player.is_home === isHome && !player.is_substitute);
  const bench = detail.lineups.filter((player) => player.is_home === isHome && player.is_substitute);
  const positioned = positionedPlayers(starters);
  const dots = formationDots(formation);

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex min-w-0 items-center gap-3">
          <FootballBadge name={team.name} url={team.badge_url} size={38} />
          <div className="min-w-0">
            <h3 className="truncate text-sm font-semibold text-text">{team.name}</h3>
            <p className="text-xs text-subtext0">{formation ? `${formation} published formation` : 'Formation not published'}</p>
          </div>
        </div>
        <div className="text-right text-xs text-subtext0">
          <p className="font-semibold text-subtext1">Coach</p>
          <p>{coach || 'Not supplied'}</p>
        </div>
      </div>

      <div className="relative mx-auto aspect-[2/3] w-full max-w-md overflow-hidden rounded-[1.6rem] border-2 border-white/30 bg-[#176f46] shadow-inner">
        <div className="absolute inset-3 rounded-2xl border border-white/55" />
        <div className="absolute inset-x-3 top-1/2 border-t border-white/55" />
        <div className="absolute left-1/2 top-1/2 size-20 -translate-x-1/2 -translate-y-1/2 rounded-full border border-white/55" />
        <div className="absolute left-1/2 top-3 h-16 w-36 -translate-x-1/2 border border-t-0 border-white/55" />
        <div className="absolute bottom-3 left-1/2 h-16 w-36 -translate-x-1/2 border border-b-0 border-white/55" />

        {!positioned.length ? dots.map((dot) => (
          <span
            key={dot.key}
            className="absolute size-3 -translate-x-1/2 -translate-y-1/2 rounded-full border-2 border-white/80 bg-white/25"
            style={{ left: `${dot.left}%`, top: `${dot.top}%` }}
            aria-hidden="true"
          />
        )) : null}

        {positioned.map(({ player, left, top }) => (
          <div
            key={`${player.player_id}-${player.player}`}
            className="absolute w-20 -translate-x-1/2 -translate-y-1/2 text-center"
            style={{ left: `${left}%`, top: `${top}%` }}
          >
            <span className="mx-auto flex size-8 items-center justify-center overflow-hidden rounded-full border-2 border-white bg-[#0c3d2a] shadow-lg">
              {player.cutout_url ? <PlayerAvatar name={player.player || 'Player'} image_url={player.cutout_url} size={28} ring={false} /> : <span className="text-[10px] font-semibold text-white">{player.shirt_number || '•'}</span>}
            </span>
            <span className="mt-1 block truncate rounded-md bg-black/70 px-1 py-0.5 text-[9px] font-bold text-white">{player.player || 'Unnamed'}</span>
            <span className="mt-0.5 block truncate text-[8px] text-white/80">{player.position || 'Role unavailable'}</span>
          </div>
        ))}

        {!positioned.length && !dots.length ? (
          <div className="absolute inset-0 flex items-center justify-center p-8 text-center text-sm font-semibold text-white/80">
            No verified formation or starting XI was supplied.
          </div>
        ) : null}
      </div>

      <p className="text-xs leading-5 text-subtext0">
        {positioned.length
          ? `${positioned.length} verified starters mapped from their published roles.`
          : dots.length
            ? 'Formation shape is source-published; player names were not supplied.'
            : 'The pitch remains empty rather than guessing a formation.'}
      </p>
      {bench.length ? (
        <div>
          <h4 className="mb-2 flex items-center gap-2 text-sm font-semibold text-text"><Shirt className="size-4 text-overlay0" /> Bench</h4>
          <div className="flex flex-wrap gap-2">
            {bench.map((player) => <span key={`${player.player_id}-${player.player}`} className="rounded-md border border-surface1 px-2 py-0.5 text-xs text-subtext1">{player.player}</span>)}
          </div>
        </div>
      ) : null}
    </div>
  );
}

export function MatchDetailCentre({ detail, onBack }: { detail: MatchCentreDetailResponse; onBack: () => void }) {
  const [side, setSide] = useState<Side>('home');
  const match = detail.match;
  const isFixturePreview = match.home_goals === null && match.away_goals === null
    && !detail.lineups.length && !detail.statistics.length && !detail.timeline.length
    && !detail.home_formation && !detail.away_formation;
  const orderedTimeline = useMemo(() => [...detail.timeline].sort((a, b) => Number.parseInt(a.minute || '999', 10) - Number.parseInt(b.minute || '999', 10)), [detail.timeline]);

  return (
    <div className="space-y-5">
      <Button variant="outline" size="sm" onPress={onBack} className="gap-2"><ArrowLeft className="size-4" />Back to matches</Button>

      <Card className="overflow-hidden rounded-xl border border-surface1 bg-surface0">
        <div className="border-b border-surface1 p-5 sm:p-6">
          <div className="mb-5 flex flex-wrap items-center justify-between gap-3 text-xs text-subtext0">
            <span className="flex items-center gap-2"><CalendarDays className="size-4" />{match.match_date}{match.kickoff_time ? ` · Kickoff ${match.kickoff_time}` : ''} · {match.competition}</span>
            <span>{detail.status || match.stage || 'Match record'}</span>
          </div>
          <div className="grid grid-cols-[1fr_auto_1fr] items-center gap-3 sm:gap-8">
            <div className="flex min-w-0 flex-col items-center gap-2 text-center sm:flex-row sm:justify-end sm:text-right">
              <span className="truncate text-sm font-semibold text-text sm:text-lg">{match.home.name}</span>
              <FootballBadge name={match.home.name} url={match.home.badge_url} size={48} />
            </div>
            <div className="rounded-lg bg-mantle px-4 py-2 text-2xl font-semibold tabular-nums text-text sm:px-5 sm:text-3xl">
              {match.home_goals ?? '–'}<span className="px-2 text-overlay0">:</span>{match.away_goals ?? '–'}
            </div>
            <div className="flex min-w-0 flex-col items-center gap-2 text-center sm:flex-row sm:text-left">
              <FootballBadge name={match.away.name} url={match.away.badge_url} size={48} />
              <span className="truncate text-sm font-semibold text-text sm:text-lg">{match.away.name}</span>
            </div>
          </div>
          <div className="mt-5 flex flex-wrap justify-center gap-x-5 gap-y-2 text-xs text-subtext0">
            {detail.stadium ? <span className="flex items-center gap-1.5"><MapPin className="size-3.5" />{detail.stadium}</span> : null}
            {detail.attendance ? <span className="flex items-center gap-1.5"><UsersRound className="size-3.5" />{detail.attendance.toLocaleString()} attendance</span> : null}
            {match.referee ? <span className="flex items-center gap-1.5"><UserRound className="size-3.5" />{match.referee}</span> : null}
          </div>
        </div>

        {isFixturePreview ? (
          <section className="space-y-5 p-5 sm:p-6">
            <div>
              <h2 className="text-sm font-semibold text-text">Fixture preview</h2>
              <p className="mt-2 max-w-2xl text-sm leading-6 text-subtext1">
                This match has not produced a verified result or match events yet. The fixture information below is what the source has published.
              </p>
            </div>
            <dl className="grid gap-4 rounded-lg border border-surface1 bg-mantle p-4 text-sm sm:grid-cols-2">
              <div><dt className="text-subtext0">Date</dt><dd className="font-semibold text-text">{match.match_date}</dd></div>
              <div><dt className="text-subtext0">Kickoff</dt><dd className="font-semibold text-text">{match.kickoff_time || 'Not announced'}</dd></div>
              <div><dt className="text-subtext0">Competition</dt><dd className="font-semibold text-text">{match.competition}</dd></div>
              <div><dt className="text-subtext0">Venue</dt><dd className="font-semibold text-text">{detail.stadium || match.venue || 'Not announced'}</dd></div>
              {match.stage ? <div><dt className="text-subtext0">Stage</dt><dd className="font-semibold text-text">{match.stage}</dd></div> : null}
              {match.referee ? <div><dt className="text-subtext0">Referee</dt><dd className="font-semibold text-text">{match.referee}</dd></div> : null}
              {detail.home_coach ? <div><dt className="text-subtext0">{match.home.name} coach</dt><dd className="font-semibold text-text">{detail.home_coach}</dd></div> : null}
              {detail.away_coach ? <div><dt className="text-subtext0">{match.away.name} coach</dt><dd className="font-semibold text-text">{detail.away_coach}</dd></div> : null}
            </dl>
            {detail.narrative.length ? <div className="space-y-2 text-sm leading-6 text-subtext1">{detail.narrative.map((line) => <p key={line}>{line}</p>)}</div> : null}
            {detail.coverage_notes.length ? <div className="rounded-lg border border-warning/30 bg-warning/5 p-4"><h3 className="mb-2 text-sm font-semibold text-warning">Data coverage</h3><ul className="space-y-1 text-xs leading-5 text-subtext1">{detail.coverage_notes.map((note) => <li key={note}>• {note}</li>)}</ul></div> : null}
            <SourceBadge meta={detail.source} />
          </section>
        ) : <div className="grid xl:grid-cols-[1.05fr_0.95fr]">
          <div className="border-b border-surface1 p-4 sm:p-6 xl:border-b-0 xl:border-r">
            <div className="mb-5 flex rounded-lg border border-surface1 bg-mantle p-0.5">
              {(['home', 'away'] as Side[]).map((value) => {
                const team = value === 'home' ? match.home : match.away;
                return <Button key={value} size="sm" variant={side === value ? 'primary' : 'ghost'} onPress={() => setSide(value)} className="flex-1">{team.name}</Button>;
              })}
            </div>
            <Pitch detail={detail} side={side} />
          </div>

          <div className="divide-y divide-surface1">
            <section className="p-4 sm:p-6">
              <h2 className="mb-3 text-sm font-semibold text-text">Match overview</h2>
              {detail.narrative.length ? (
                <div className="space-y-2 text-sm leading-6 text-subtext1">
                  {detail.narrative.map((line) => <p key={line}>{line}</p>)}
                </div>
              ) : <p className="text-sm text-subtext0">No factual summary can be built from the available fields.</p>}
            </section>

            <section className="p-4 sm:p-6">
              <h2 className="mb-4 text-sm font-semibold text-text">Match statistics</h2>
              <div className="space-y-4">
                {detail.statistics.map((stat) => {
                  const home = stat.home_value ?? 0;
                  const away = stat.away_value ?? 0;
                  const total = Math.max(home + away, 1);
                  return (
                    <div key={stat.statistic}>
                      <div className="mb-1.5 grid grid-cols-[3rem_1fr_3rem] items-center text-xs">
                        <span className="font-semibold tabular-nums text-text">{stat.home_value ?? '—'}</span>
                        <span className="text-center font-semibold text-subtext1">{stat.statistic}</span>
                        <span className="text-right font-semibold tabular-nums text-text">{stat.away_value ?? '—'}</span>
                      </div>
                      <div className="flex h-2 overflow-hidden rounded-full bg-surface1"><span style={{ background: 'var(--outcome-home)',  width: `${home / total * 100}%` }} /><span style={{ background: 'var(--outcome-away)',  width: `${away / total * 100}%` }} /></div>
                    </div>
                  );
                })}
                {!detail.statistics.length ? <p className="text-sm text-subtext0">No verified statistics were supplied.</p> : null}
              </div>
            </section>
          </div>
        </div>}
      </Card>

      {!isFixturePreview ? <div className="grid gap-5 lg:grid-cols-[1fr_0.72fr]">
        <Card className="rounded-xl border border-surface1 bg-surface0 p-4 sm:p-5">
          <h2 className="mb-5 flex items-center gap-2 text-sm font-semibold text-text"><Timer className="size-4 text-overlay0" />Match timeline</h2>
          {orderedTimeline.length ? (
            <div className="relative space-y-1 before:absolute before:bottom-4 before:left-[2.2rem] before:top-4 before:w-px before:bg-surface2">
              {orderedTimeline.map((item, index) => (
                <div key={`${item.minute}-${item.player_id}-${index}`} className="relative grid grid-cols-[4.5rem_1fr] gap-3 py-2">
                  <span className="z-10 flex size-9 items-center justify-center rounded-full border border-surface2 bg-mantle text-xs font-semibold tabular-nums text-text">{item.minute ? `${item.minute}′` : '•'}</span>
                  <div className="rounded-xl border border-surface1 bg-mantle/60 p-3">
                    <div className="flex items-center gap-2">
                      <span className={`flex size-7 shrink-0 items-center justify-center rounded-lg border text-xs font-semibold ${timelineMark(item.event_type).tone}`}>{timelineMark(item.event_type).mark}</span>
                      <FootballBadge name={item.team.name} url={item.team.badge_url} size={20} />
                      <div className="min-w-0"><p className="truncate font-medium text-text">{item.player || item.event_type || 'Match event'}</p><p className="text-[10px] text-subtext0">{item.team.name}</p></div>
                    </div>
                    <p className="mt-2 text-xs text-subtext0">{item.event_type}{item.detail ? ` · ${item.detail}` : ''}{item.assist ? ` · ${item.event_type?.toLowerCase().includes('substitution') ? 'Player in' : 'Assist'}: ${item.assist}` : ''}</p>
                    {item.comment ? <p className="mt-1 text-xs text-subtext1">{item.comment}</p> : null}
                  </div>
                </div>
              ))}
            </div>
          ) : <p className="text-sm text-subtext0">No verified event timeline was supplied for this match.</p>}
        </Card>

        <div className="space-y-5">
          <Card className="rounded-xl border border-surface1 bg-surface0 p-4">
            <h2 className="mb-3 text-[16px] font-semibold text-text">Technical area</h2>
            <div className="space-y-3 text-sm">
              <div className="flex justify-between gap-3"><span className="text-subtext0">{match.home.name}</span><span className="text-right font-semibold text-text">{detail.home_coach || 'Coach unavailable'} · {detail.home_formation || 'shape unavailable'}</span></div>
              <div className="flex justify-between gap-3"><span className="text-subtext0">{match.away.name}</span><span className="text-right font-semibold text-text">{detail.away_coach || 'Coach unavailable'} · {detail.away_formation || 'shape unavailable'}</span></div>
            </div>
          </Card>
          {detail.coverage_notes.length ? (
            <Card className="rounded-xl border border-warning/30 bg-warning/5 p-4">
              <h2 className="mb-3 flex items-center gap-2 text-sm font-semibold text-warning"><CircleAlert className="size-4" />Data coverage</h2>
              <ul className="space-y-2 text-xs leading-5 text-subtext1">{detail.coverage_notes.map((note) => <li key={note}>• {note}</li>)}</ul>
            </Card>
          ) : null}
          <SourceBadge meta={detail.source} />
        </div>
      </div> : null}
    </div>
  );
}
