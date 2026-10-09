'use client';

import React, { useEffect, useRef, useState } from 'react';
import { useTheme, AVAILABLE_THEMES } from '@/components/theme-provider';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Button, Card } from '@heroui/react';
import { api } from '@/lib/api/client';
import { queryKeys } from '@/lib/api/query-keys';
import { PageHeader } from '@/components/ui/page-header';
import {
  Palette,
  Sun,
  Moon,
  Laptop,
  Check,
  Server,
  Activity,
  Database,
  Sliders,
  RefreshCw,
  CloudDownload,
  CircleCheck,
} from 'lucide-react';

const REFRESH_STEPS = [
  { title: 'Results and fixtures', detail: 'Current scorelines, verified full calendars and nearby fixtures' },
  { title: 'Tables and competitions', detail: 'Reference standings and selected tournaments' },
  { title: 'Teams, players and match detail', detail: 'Artwork, squads, formations and event data' },
  { title: 'Models and validation', detail: 'Analytics caches and calibrated predictions' },
];

export default function SettingsPage() {
  const { theme, mode, setTheme, setMode } = useTheme();
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

  return (
    <div className="mx-auto max-w-5xl space-y-8">
      <PageHeader icon={Sliders} eyebrow="Workspace preferences" title="Application Settings" description="Choose an accessible theme, verify the API and guide a safe source-data refresh from one place." />

      {/* Section 1: Appearance Mode */}
      <div className="rounded-xl border border-surface1 bg-surface0 p-6 space-y-4">
        <div className="flex items-center gap-2.5 pb-2 border-b border-surface1">
          <Palette className="h-5 w-5 text-blue" />
          <h2 className="text-base font-semibold text-text">Theme Mode & Auto-Detection</h2>
        </div>

        <p className="text-xs text-subtext0">
          Select whether the theme automatically adapts to your operating system or stays permanently dark or light.
        </p>

        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 pt-1">
          {/* Auto */}
          <button
            type="button"
            aria-pressed={mode === 'auto'}
            onClick={() => setMode('auto')}
            className={`flex items-center gap-3 p-4 rounded-xl border text-left transition-all cursor-pointer ${
              mode === 'auto'
                ? 'bg-blue/15 border-blue text-text shadow-sm'
                : 'bg-mantle border-surface1 text-subtext1 hover:bg-surface1'
            }`}
          >
            <Laptop className={`h-5 w-5 ${mode === 'auto' ? 'text-blue' : 'text-subtext0'}`} />
            <div>
              <p className="text-sm font-semibold">Automatic</p>
              <p className="text-xs text-subtext0 mt-0.5">Sync with system</p>
            </div>
          </button>

          {/* Dark */}
          <button
            type="button"
            aria-pressed={mode === 'dark'}
            onClick={() => setMode('dark')}
            className={`flex items-center gap-3 p-4 rounded-xl border text-left transition-all cursor-pointer ${
              mode === 'dark'
                ? 'bg-blue/15 border-blue text-text shadow-sm'
                : 'bg-mantle border-surface1 text-subtext1 hover:bg-surface1'
            }`}
          >
            <Moon className={`h-5 w-5 ${mode === 'dark' ? 'text-blue' : 'text-subtext0'}`} />
            <div>
              <p className="text-sm font-semibold">Force Dark</p>
              <p className="text-xs text-subtext0 mt-0.5">Dark background</p>
            </div>
          </button>

          {/* Light */}
          <button
            type="button"
            aria-pressed={mode === 'light'}
            onClick={() => setMode('light')}
            className={`flex items-center gap-3 p-4 rounded-xl border text-left transition-all cursor-pointer ${
              mode === 'light'
                ? 'bg-blue/15 border-blue text-text shadow-sm'
                : 'bg-mantle border-surface1 text-subtext1 hover:bg-surface1'
            }`}
          >
            <Sun className={`h-5 w-5 ${mode === 'light' ? 'text-blue' : 'text-subtext0'}`} />
            <div>
              <p className="text-sm font-semibold">Force Light</p>
              <p className="text-xs text-subtext0 mt-0.5">Light background</p>
            </div>
          </button>
        </div>
      </div>

      {/* Section 2: 6 Theme Palettes */}
      <div className="rounded-xl border border-surface1 bg-surface0 p-6 space-y-4">
        <div className="flex items-center justify-between pb-2 border-b border-surface1">
          <div className="flex items-center gap-2.5">
            <Sliders className="h-5 w-5 text-teal" />
            <h2 className="text-base font-semibold text-text">Color Palettes ({AVAILABLE_THEMES.length} Available)</h2>
          </div>
          <span className="text-xs text-subtext0">
            Active: <strong className="text-text capitalize">{theme.replace('-', ' ')}</strong>
          </span>
        </div>

        <p className="text-xs text-subtext0">
          Choose from custom tailored designer palettes with carefully balanced contrast and accent colors.
        </p>

        <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-3.5 pt-2">
          {AVAILABLE_THEMES.map((opt) => {
            const isSelected = theme === opt.id;
            return (
              <button
                key={opt.id}
                type="button"
                aria-pressed={isSelected}
                onClick={() => setTheme(opt.id)}
                className={`flex flex-col justify-between p-4 rounded-xl border transition-all text-left cursor-pointer ${
                  isSelected
                    ? 'border-blue ring-2 ring-blue/30 shadow-md'
                    : 'border-surface1 hover:border-surface2'
                }`}
                style={{ backgroundColor: opt.previewBg }}
              >
                <div className="flex items-center justify-between w-full mb-3">
                  <div className="flex items-center gap-2">
                    <span
                      className="h-3 w-3 rounded-full"
                      style={{ backgroundColor: opt.accent }}
                    />
                    <span
                      className="text-xs font-bold"
                      style={{ color: opt.previewText }}
                    >
                      {opt.name}
                    </span>
                  </div>
                  {isSelected && (
                    <span className="p-0.5 rounded-full bg-blue text-crust">
                      <Check className="h-3 w-3" />
                    </span>
                  )}
                </div>

                <div className="flex items-center justify-between text-[11px]">
                  <span style={{ color: opt.previewText }} className="capitalize font-mono">
                    {opt.type}
                  </span>
                  <div className="flex gap-1">
                    <span className="h-2 w-4 rounded-xs" style={{ backgroundColor: opt.accent }} />
                    <span className="h-2 w-2 rounded-xs" style={{ backgroundColor: opt.previewText }} />
                  </div>
                </div>
              </button>
            );
          })}
        </div>
      </div>

      {/* Section 3: Pagination & Display Settings */}
      <div className="rounded-xl border border-surface1 bg-surface0 p-6 space-y-4">
        <h2 className="text-base font-semibold text-text pb-2 border-b border-surface1">
          Display & Pagination Standards
        </h2>
        <div className="space-y-3 text-xs text-subtext1">
          <div className="flex items-center justify-between py-2 border-b border-surface1/50">
            <div>
              <p className="font-semibold text-text">Standard Page Size</p>
              <p className="text-subtext0 text-[11px]">Enforced across all data views exceeding 10 entries</p>
            </div>
            <span className="font-mono font-bold text-blue px-2.5 py-1 rounded bg-mantle border border-surface1">
              10 entries / page
            </span>
          </div>

          <div className="flex items-center justify-between py-2 border-b border-surface1/50">
            <div>
              <p className="font-semibold text-text">URL Filter Persistence</p>
              <p className="text-subtext0 text-[11px]">Retain competition, season, club and stage in query params</p>
            </div>
            <span className="font-semibold text-green">Enabled</span>
          </div>

          <div className="flex items-center justify-between py-2">
            <div>
              <p className="font-semibold text-text">Color Token Architecture</p>
              <p className="text-subtext0 text-[11px]">CSS custom properties with Tailwind v4 runtime switching</p>
            </div>
            <span className="font-semibold text-teal">Active</span>
          </div>
        </div>
      </div>

      {/* Section 4: Backend API Diagnostics */}
      <Card className="overflow-hidden rounded-2xl border border-surface1 bg-surface0">
        <div className="border-b border-surface1 p-5 sm:p-6">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div>
              <div className="flex items-center gap-2.5">
                <CloudDownload className="size-5 text-teal" />
                <h2 className="text-base font-semibold text-text">Gather fresh data</h2>
              </div>
              <p className="mt-2 max-w-2xl text-xs leading-5 text-subtext0">Choose how deep the refresh should run. Each level includes the steps before it. Completed stages are saved as they finish, so an interrupted run can be resumed.</p>
            </div>
            <span className={`rounded-full px-3 py-1 text-xs font-bold ${refreshStatus?.status === 'running' || refreshStatus?.status === 'degraded' ? 'bg-yellow/15 text-yellow' : refreshStatus?.status === 'success' ? 'bg-green/15 text-green' : refreshStatus?.status === 'failed' ? 'bg-red/15 text-red' : 'bg-surface1 text-subtext1'}`}>
              {refreshStatus?.status || 'idle'}
            </span>
          </div>
        </div>

        <div className="space-y-6 p-5 sm:p-6">
          <div>
            <div className="mb-3 flex items-center justify-between text-sm"><span className="font-semibold text-text">Refresh depth</span><span className="font-mono font-black text-teal">Step {refreshDepth} of 4</span></div>
            <input
              aria-label="Refresh depth"
              type="range"
              min={1}
              max={4}
              step={1}
              value={refreshDepth}
              onChange={(event) => setRefreshDepth(Number(event.target.value))}
              disabled={refreshStatus?.status === 'running'}
              className="h-2 w-full cursor-pointer accent-[var(--teal)] disabled:cursor-not-allowed"
            />
            <div className="mt-4 grid gap-2 sm:grid-cols-2 lg:grid-cols-4">
              {REFRESH_STEPS.map((step, index) => {
                const number = index + 1;
                const included = number <= refreshDepth;
                const complete = refreshStatus?.completed_steps.includes(number);
                return (
                  <button key={step.title} type="button" onClick={() => setRefreshDepth(number)} disabled={refreshStatus?.status === 'running'} className={`rounded-xl border p-3 text-left transition-colors ${included ? 'border-teal/40 bg-teal/5' : 'border-surface1 bg-mantle opacity-55'}`}>
                    <span className="mb-2 flex size-6 items-center justify-center rounded-full bg-surface1 text-xs font-black text-text">{complete ? <CircleCheck className="size-4 text-green" /> : number}</span>
                    <span className="block text-xs font-bold text-text">{step.title}</span>
                    <span className="mt-1 block text-[11px] leading-4 text-subtext0">{step.detail}</span>
                  </button>
                );
              })}
            </div>
          </div>

          <div className="grid gap-5 border-t border-surface1 pt-5 md:grid-cols-[0.38fr_1fr]">
            <label className="space-y-1 text-xs font-semibold text-subtext1">
              Season start year
              <input type="number" min={2010} max={2100} value={refreshSeason ?? catalog?.current_season ?? ''} onChange={(event) => setRefreshSeason(Number(event.target.value))} className="mt-1 min-h-10 w-full rounded-xl border border-surface1 bg-mantle px-3 text-sm text-text outline-none focus:border-blue" />
            </label>
            <div>
              <p className="mb-2 text-xs font-semibold text-subtext1">Competitions <span className="font-normal text-subtext0">— none selected means all domestic leagues</span></p>
              <div className="flex flex-wrap gap-2">
                {(catalog?.competitions || []).map((competition) => {
                  const active = refreshCompetitions.includes(competition.code);
                  return <Button key={competition.code} size="sm" variant={active ? 'primary' : 'outline'} onPress={() => setRefreshCompetitions((current) => active ? current.filter((code) => code !== competition.code) : [...current, competition.code])}>{competition.name}</Button>;
                })}
              </div>
            </div>
          </div>

          <label className="flex items-center gap-3 text-xs text-subtext1">
            <input type="checkbox" checked={forceDownload} onChange={(event) => setForceDownload(event.target.checked)} className="size-4 accent-[var(--blue)]" />
            Force all sources to download again (slower; normal refresh checks freshness automatically)
          </label>

          {refreshStatus && refreshStatus.status !== 'idle' ? (
            <div className="rounded-xl border border-surface1 bg-mantle p-4">
              <div className="mb-2 flex items-center justify-between gap-3 text-xs"><span className="font-bold text-text">{refreshStatus.step_name}</span><span className="font-mono text-subtext0">{refreshStatus.current_step}/{refreshStatus.target_step}</span></div>
              <div className="mb-3 h-1.5 overflow-hidden rounded-full bg-surface1"><div className={`h-full ${refreshStatus.status === 'failed' ? 'bg-red' : refreshStatus.status === 'success' ? 'bg-green' : 'bg-teal'}`} style={{ width: `${Math.max(4, refreshStatus.current_step / refreshStatus.target_step * 100)}%` }} /></div>
              <p className="text-xs leading-5 text-subtext0">{refreshStatus.message}</p>
              {refreshStatus.source_messages?.length ? (
                <ul className="mt-2 list-disc space-y-1 pl-5 text-xs text-yellow" aria-label="Source refresh problems">
                  {refreshStatus.source_messages.map((message, index) => <li key={`${index}-${message}`}>{message}</li>)}
                </ul>
              ) : null}
            </div>
          ) : null}

          <div className="flex flex-wrap items-center justify-between gap-3">
            <p className="max-w-xl text-[11px] leading-4 text-subtext0">API reads pause during refresh. Completed stages remain applied if a later stage fails; source partitions are individually protected.</p>
            <Button
              variant="primary"
              isDisabled={!(refreshSeason ?? catalog?.current_season) || refreshStatus?.status === 'running'}
              onPress={() => refreshMutation.mutate({ target_step: refreshDepth, season: refreshSeason ?? catalog?.current_season, competitions: refreshCompetitions, force_download: forceDownload })}
              className="gap-2"
            >
              <RefreshCw className={`size-4 ${refreshMutation.isPending || refreshStatus?.status === 'running' ? 'animate-spin' : ''}`} />Gather data through step {refreshDepth}
            </Button>
          </div>
          {refreshMutation.error ? <p className="text-xs text-red">{refreshMutation.error.message}</p> : null}
        </div>
      </Card>

      <div className="rounded-xl border border-surface1 bg-surface0 p-6 space-y-4">
        <div className="flex items-center justify-between pb-2 border-b border-surface1">
          <div className="flex items-center gap-2.5">
            <Server className="h-5 w-5 text-peach" />
            <h2 className="text-base font-semibold text-text">Backend API Diagnostics</h2>
          </div>
          <button
            onClick={() => {
              refetchHealth();
              testPing();
            }}
            disabled={isPinging}
            className="flex items-center gap-1.5 px-3 py-1 text-xs rounded bg-mantle border border-surface1 hover:border-surface2 text-text transition-colors cursor-pointer"
          >
            <RefreshCw className={`h-3 w-3 text-blue ${isPinging ? 'animate-spin' : ''}`} />
            <span>Test Connection</span>
          </button>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
          <div className="rounded-lg bg-mantle p-3.5 border border-surface1">
            <div className="flex items-center justify-between text-subtext0 text-xs">
              <span>Service Status</span>
              <span className={`h-2.5 w-2.5 rounded-full ${health?.status === 'ok' ? 'bg-green' : 'bg-red'}`} />
            </div>
            <p className="text-lg font-bold text-text mt-1 capitalize">{health?.status || 'Connecting…'}</p>
          </div>

          <div className="rounded-lg bg-mantle p-3.5 border border-surface1">
            <div className="flex items-center justify-between text-subtext0 text-xs">
              <span>Ping Latency</span>
              <Activity className="h-3.5 w-3.5 text-blue" />
            </div>
            <p className="text-lg font-bold text-text mt-1">
              {pingLatency !== null ? (pingLatency >= 0 ? `${pingLatency} ms` : 'Failed') : 'Untested'}
            </p>
          </div>

          <div className="rounded-lg bg-mantle p-3.5 border border-surface1">
            <div className="flex items-center justify-between text-subtext0 text-xs">
              <span>Database Access</span>
              <Database className="h-3.5 w-3.5 text-teal" />
            </div>
            <p className="text-sm font-semibold text-text mt-1 truncate" title={health?.database}>
              {health?.read_only ? 'DuckDB (Read-Only)' : 'DuckDB'}
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
