'use client';

import React, { useEffect, useRef, useState } from 'react';
import { useTheme } from '@/components/theme-provider';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Button } from '@heroui/react';
import { api } from '@/lib/api/client';
import { queryKeys } from '@/lib/api/query-keys';
import { PageHeader } from '@/components/ui/page-header';
import { Sun, Moon, Laptop, Sliders, RefreshCw, CircleCheck } from 'lucide-react';
import { Panel } from '@/components/ui/panel';
import { Stat } from '@/components/ui/stat';
import { Chip } from '@/components/ui/chip';

const REFRESH_STEPS = [
  { title: 'Results and fixtures', detail: 'Current scorelines, verified full calendars and nearby fixtures' },
  { title: 'Tables and competitions', detail: 'Reference standings and selected tournaments' },
  { title: 'Teams, players and match detail', detail: 'Artwork, squads, formations and event data' },
  { title: 'Models and validation', detail: 'Analytics caches and calibrated predictions' },
];

export default function SettingsPage() {
  const { mode, setMode } = useTheme();
  const [pingLatency, setPingLatency] = useState<number | null>(null);
  const [isPinging, setIsPinging] = useState(false);
  const [refreshDepth, setRefreshDepth] = useState(4);
  const [refreshSeason, setRefreshSeason] = useState<number | null>(null);
  const [refreshCompetitions, setRefreshCompetitions] = useState<string[]>([]);
  const [forceDownload, setForceDownload] = useState(false);
  const queryClient = useQueryClient();

  const { data: health, refetch: refetchHealth } = useQuery({
    queryKey: queryKeys.health,
    queryFn: () => api.health(),
  });
  const { data: catalog } = useQuery({ queryKey: queryKeys.catalog, queryFn: api.catalog });
  const { data: refreshStatus } = useQuery({
    queryKey: queryKeys.refreshStatus,
    queryFn: api.refreshStatus,
    refetchInterval: (query) => query.state.data?.status === 'running' ? 1000 : 5000,
  });
  const refreshMutation = useMutation({
    mutationFn: api.startRefresh,
    onSuccess: (status) => queryClient.setQueryData(queryKeys.refreshStatus, status),
  });

  // Refetch app data only when a refresh finishes while this page is open; the stored status of
  // an earlier run (seen on first load) must not invalidate every query on each visit.
  const seenFinish = useRef<string | null | undefined>(undefined);
  useEffect(() => {
    const finished = refreshStatus?.status === 'success' || refreshStatus?.status === 'degraded' || refreshStatus?.status === 'failed';
    if (refreshStatus === undefined) return;
    const stamp = finished ? refreshStatus.finished_at : null;
    if (seenFinish.current !== undefined && stamp && stamp !== seenFinish.current) {
      queryClient.invalidateQueries({ predicate: (query) => query.queryKey[0] !== 'refresh-status' });
    }
    seenFinish.current = stamp;
  }, [queryClient, refreshStatus]);

  const testPing = async () => {
    setIsPinging(true);
    const start = performance.now();
    try {
      await api.health();
      const end = performance.now();
      setPingLatency(Math.round(end - start));
    } catch {
      setPingLatency(-1);
    } finally {
      setIsPinging(false);
    }
  };

  const statusTone = refreshStatus?.status === 'success' ? 'positive' : refreshStatus?.status === 'failed' ? 'negative'
    : refreshStatus?.status === 'running' || refreshStatus?.status === 'degraded' ? 'warning' : 'neutral';
  const running = refreshStatus?.status === 'running';
  const modes = [
    { value: 'auto', label: 'Automatic', hint: 'Follow the system', icon: Laptop },
    { value: 'dark', label: 'Dark', hint: 'Always dark', icon: Moon },
    { value: 'light', label: 'Light', hint: 'Always light', icon: Sun },
  ] as const;

  return (
    <div className="mx-auto max-w-5xl space-y-5">
      <PageHeader icon={Sliders} eyebrow="Workspace preferences" title="Application Settings" description="Choose light or dark mode, verify the API and guide a safe source-data refresh from one place." />

      <Panel title="Appearance" description="Follow your system setting, or keep the interface dark or light.">
        <div className="grid grid-cols-1 gap-2 sm:grid-cols-3">
          {modes.map((option) => {
            const active = mode === option.value;
            const Icon = option.icon;
            return (
              <button key={option.value} type="button" aria-pressed={active} onClick={() => setMode(option.value)}
                className={`flex items-center gap-3 rounded-lg border px-3 py-2.5 text-left transition-colors ${active ? 'border-accent bg-accent/10' : 'border-surface1 hover:bg-surface1/40'}`}>
                <Icon className={`size-4 ${active ? 'text-accent' : 'text-overlay0'}`} aria-hidden="true" />
                <span>
                  <span className="block text-[13px] font-medium text-text">{option.label}</span>
                  <span className="block text-xs text-subtext0">{option.hint}</span>
                </span>
              </button>
            );
          })}
        </div>
      </Panel>

      <Panel
        title="Gather fresh data"
        description="Choose how deep the refresh should run. Each level includes the steps before it. Completed stages are saved as they finish, so an interrupted run can be resumed."
        actions={<Chip tone={statusTone}>{refreshStatus?.status || 'idle'}</Chip>}
        bodyClassName="space-y-5"
      >
        <div>
          <div className="mb-2 flex items-center justify-between text-[13px]">
            <span className="font-medium text-text">Refresh depth</span>
            <span className="font-medium tabular-nums text-accent">Step {refreshDepth} of 4</span>
          </div>
          <input aria-label="Refresh depth" type="range" min={1} max={4} step={1} value={refreshDepth}
            onChange={(event) => setRefreshDepth(Number(event.target.value))} disabled={running}
            className="h-1.5 w-full cursor-pointer accent-[var(--blue)] disabled:cursor-not-allowed" />
          <div className="mt-3 grid gap-2 sm:grid-cols-2 lg:grid-cols-4">
            {REFRESH_STEPS.map((step, index) => {
              const number = index + 1;
              const included = number <= refreshDepth;
              const complete = refreshStatus?.completed_steps.includes(number);
              return (
                <button key={step.title} type="button" onClick={() => setRefreshDepth(number)} disabled={running}
                  className={`rounded-lg border p-3 text-left transition-colors ${included ? 'border-accent/50 bg-accent/5' : 'border-surface1 opacity-60 hover:opacity-100'}`}>
                  <span className="mb-1.5 flex size-5 items-center justify-center rounded-full bg-surface1 text-xs font-medium tabular-nums text-text">
                    {complete ? <CircleCheck className="size-3.5 text-positive" aria-hidden="true" /> : number}
                  </span>
                  <span className="block text-[13px] font-medium text-text">{step.title}</span>
                  <span className="mt-0.5 block text-xs leading-4 text-subtext0">{step.detail}</span>
                </button>
              );
            })}
          </div>
        </div>

        <div className="grid gap-4 border-t border-surface1 pt-4 md:grid-cols-[12rem_1fr]">
          <label className="flex flex-col gap-1 text-xs font-medium text-subtext0">
            Season start year
            <input type="number" min={2010} max={2100} value={refreshSeason ?? catalog?.current_season ?? ''}
              onChange={(event) => setRefreshSeason(Number(event.target.value))}
              className="h-9 rounded-lg border border-surface1 bg-surface0 px-3 text-[13px] text-text focus:border-accent" />
          </label>
          <div>
            <p className="mb-1.5 text-xs font-medium text-subtext0">Competitions <span className="font-normal">— none selected means all domestic leagues</span></p>
            <div className="flex flex-wrap gap-1.5">
              {(catalog?.competitions || []).map((competition) => {
                const active = refreshCompetitions.includes(competition.code);
                return (
                  <button key={competition.code} type="button" aria-pressed={active}
                    onClick={() => setRefreshCompetitions((current) => active ? current.filter((code) => code !== competition.code) : [...current, competition.code])}
                    className={`h-7 rounded-md border px-2 text-xs font-medium transition-colors ${active ? 'border-accent bg-accent/10 text-text' : 'border-surface1 text-subtext0 hover:text-text'}`}>
                    {competition.name}
                  </button>
                );
              })}
            </div>
          </div>
        </div>

        <label className="flex items-center gap-2.5 text-xs text-subtext1">
          <input type="checkbox" checked={forceDownload} onChange={(event) => setForceDownload(event.target.checked)} className="size-4 accent-[var(--blue)]" />
          Force all sources to download again (slower; a normal refresh checks freshness automatically)
        </label>

        {refreshStatus && refreshStatus.status !== 'idle' ? (
          <div className="rounded-lg border border-surface1 bg-mantle p-3">
            <div className="mb-2 flex items-center justify-between gap-3 text-xs">
              <span className="font-medium text-text">{refreshStatus.step_name}</span>
              <span className="tabular-nums text-subtext0">{refreshStatus.current_step}/{refreshStatus.target_step}</span>
            </div>
            <div className="mb-2 h-1 overflow-hidden rounded-full bg-surface1">
              <div className={`h-full ${refreshStatus.status === 'failed' ? 'bg-negative' : refreshStatus.status === 'success' ? 'bg-positive' : 'bg-accent'}`}
                style={{ width: `${Math.max(4, refreshStatus.current_step / refreshStatus.target_step * 100)}%` }} />
            </div>
            <p className="text-xs leading-5 text-subtext0">{refreshStatus.message}</p>
            {refreshStatus.source_messages?.length ? (
              <ul className="mt-2 list-disc space-y-1 pl-5 text-xs text-warning" aria-label="Source refresh problems">
                {refreshStatus.source_messages.map((message, index) => <li key={`${index}-${message}`}>{message}</li>)}
              </ul>
            ) : null}
          </div>
        ) : null}

        <div className="flex flex-wrap items-center justify-between gap-3 border-t border-surface1 pt-4">
          <p className="max-w-xl text-xs leading-5 text-subtext0">
            The API keeps serving from PostgreSQL or the SQLite snapshot while a refresh runs. Completed stages stay applied if a later one fails. Refreshes from another machine need the server&apos;s admin token.
          </p>
          <Button variant="primary" size="sm" isDisabled={!(refreshSeason ?? catalog?.current_season) || running}
            onPress={() => refreshMutation.mutate({ target_step: refreshDepth, season: refreshSeason ?? catalog?.current_season, competitions: refreshCompetitions, force_download: forceDownload })}>
            <RefreshCw className={`size-3.5 ${refreshMutation.isPending || running ? 'animate-spin motion-reduce:animate-none' : ''}`} aria-hidden="true" />
            Gather data through step {refreshDepth}
          </Button>
        </div>
        {refreshMutation.error ? <p className="text-xs text-negative">{refreshMutation.error.message}</p> : null}
      </Panel>

      <Panel
        title="Backend API diagnostics"
        actions={<Button size="sm" variant="outline" isDisabled={isPinging} onPress={() => { refetchHealth(); testPing(); }}>
          <RefreshCw className={`size-3.5 ${isPinging ? 'animate-spin motion-reduce:animate-none' : ''}`} aria-hidden="true" /> Test connection
        </Button>}
      >
        <div className="grid grid-cols-1 gap-2 sm:grid-cols-3">
          <Stat inset label="Service status" value={<span className="capitalize">{health?.status || 'connecting…'}</span>} tone={health?.status === 'ok' ? 'positive' : 'negative'} />
          <Stat inset label="Ping latency" value={pingLatency !== null ? (pingLatency >= 0 ? `${pingLatency} ms` : 'Failed') : 'Untested'} />
          <Stat inset label="Database" value={<span className="block truncate text-[16px]" title={health?.database}>{health?.database?.startsWith('postgresql') ? 'PostgreSQL' : health?.database?.endsWith('.sqlite3') ? 'SQLite snapshot' : 'DuckDB'}</span>}
            hint={health?.read_only ? 'read-only' : undefined} />
        </div>
      </Panel>
    </div>
  );
}
