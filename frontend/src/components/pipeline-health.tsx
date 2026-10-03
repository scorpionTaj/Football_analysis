'use client';

import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { CheckCircle2, CircleAlert, CircleX, Workflow } from 'lucide-react';
import { api } from '@/lib/api/client';
import { queryKeys } from '@/lib/api/query-keys';
import type { PipelineCheck } from '@/lib/api/types';
import { ErrorMessage, LoadingSkeleton } from '@/components/ui/loading';

const LAYER_NAMES: Record<string, string> = {
  'marts.fct_match': 'Matches (all leagues, 2005+)',
  'marts.mart_team_season': 'Team seasons',
  'ml.ml_match_features': 'Model features',
  'ml.model_runs': 'Models compared',
};

function age(hours: number | null) {
  if (hours === null) return 'never loaded';
  if (hours < 1) return `${Math.max(1, Math.round(hours * 60))} min ago`;
  if (hours < 48) return `${Math.round(hours)} h ago`;
  return `${Math.round(hours / 24)} days ago`;
}

/** Status is never colour alone: each state has its own icon and words. */
function Freshness({ check }: { check: PipelineCheck }) {
  const hours = check.value;
  const state = hours === null ? 'missing' : hours <= 12 ? 'fresh' : hours <= 7 * 24 ? 'ageing' : 'stale';
  const style = { fresh: 'text-green', ageing: 'text-yellow', stale: 'text-red', missing: 'text-red' }[state];
  const Icon = state === 'fresh' ? CheckCircle2 : state === 'ageing' ? CircleAlert : CircleX;
  return (
    <li className="flex items-center justify-between gap-3 py-2">
      <span className="min-w-0 truncate text-sm text-text">{check.name.replaceAll('_', ' ')}</span>
      <span className={`flex shrink-0 items-center gap-1.5 text-xs font-semibold ${style}`}>
        <Icon className="size-3.5" aria-hidden="true" />
        {state === 'fresh' ? 'Fresh' : state === 'ageing' ? 'Ageing' : state === 'stale' ? 'Stale' : 'Missing'} · {age(hours)}
      </span>
    </li>
  );
}

export function PipelineHealth() {
  const [showAll, setShowAll] = useState(false);
  const { data, isLoading, error, refetch } = useQuery({ queryKey: queryKeys.pipeline, queryFn: () => api.pipeline() });
  if (isLoading) return <section className="rounded-2xl border border-surface1/70 bg-surface0/60 p-5"><LoadingSkeleton lines={4} /></section>;
  if (error) return <ErrorMessage title="Pipeline status could not be loaded" detail={String(error)} retry={() => refetch()} />;
  if (!data || !data.checks.length) return null;

  const tests = data.checks.filter((c) => c.kind === 'dbt_test');
  const failing = tests.filter((c) => c.status !== 'pass');
  const layers = data.checks.filter((c) => c.kind === 'layer_rows');
  const freshness = data.checks.filter((c) => c.kind === 'freshness');
  const total = data.tests_passed + data.tests_failed;
  const healthy = data.tests_failed === 0;
  const built = data.checked_at ? new Intl.DateTimeFormat(undefined, { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(data.checked_at)) : 'unknown';

  return (
    <section aria-labelledby="pipeline-title" className="rounded-2xl border border-surface1/70 bg-surface0/60 p-5 sm:p-6">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="flex min-w-0 items-start gap-3">
          <Workflow className="mt-1 size-5 shrink-0 text-blue" aria-hidden="true" />
          <div className="min-w-0">
            <h2 id="pipeline-title" className="text-lg font-bold text-text">Pipeline health</h2>
            <p className="mt-1 text-sm text-subtext0">Latest warehouse build {built}. Every dbt model and data test runs on each refresh.</p>
          </div>
        </div>
        <p className={`flex items-center gap-2 rounded-xl px-3 py-2 text-sm font-bold ${healthy ? 'bg-green/10 text-green' : 'bg-red/10 text-red'}`} aria-live="polite">
          {healthy ? <CheckCircle2 className="size-4" aria-hidden="true" /> : <CircleX className="size-4" aria-hidden="true" />}
          <span className="tabular-nums">{data.tests_passed} of {total}</span> data tests passed
        </p>
      </div>

      <div className="mt-6 grid gap-6 lg:grid-cols-3">
        <div>
          <h3 className="text-sm font-bold text-text">Data tests</h3>
          {failing.length > 0 && (
            <ul className="mt-2 space-y-1">
              {failing.map((t) => (
                <li key={t.name} className="flex items-start gap-2 text-sm text-red">
                  <CircleX className="mt-0.5 size-3.5 shrink-0" aria-hidden="true" />
                  <span className="min-w-0 break-words">{t.name} · {t.value ?? 0} failing rows</span>
                </li>
              ))}
            </ul>
          )}
          <button type="button" onClick={() => setShowAll((v) => !v)} aria-expanded={showAll}
                  className="mt-2 text-sm font-semibold text-blue hover:underline focus-visible:outline focus-visible:outline-2 focus-visible:outline-blue">
            {showAll ? 'Hide passing tests' : `Show ${data.tests_passed} passing tests`}
          </button>
          {showAll && (
            <ul className="mt-2 max-h-64 space-y-1 overflow-y-auto pr-1">
              {tests.filter((t) => t.status === 'pass').map((t) => (
                <li key={t.name} className="flex items-start gap-2 text-xs text-subtext1">
                  <CheckCircle2 className="mt-0.5 size-3 shrink-0 text-green" aria-hidden="true" />
                  <span className="min-w-0 break-words">{t.name.replaceAll('_', ' ')}</span>
                </li>
              ))}
            </ul>
          )}
        </div>
        <div>
          <h3 className="text-sm font-bold text-text">Warehouse layers</h3>
          <dl className="mt-2 divide-y divide-surface1/50">
            {layers.map((l) => (
              <div key={l.name} className="flex items-center justify-between gap-3 py-2">
                <dt className="min-w-0 truncate text-sm text-text">{LAYER_NAMES[l.name] ?? l.name}</dt>
                <dd className="text-sm font-bold tabular-nums text-subtext1">{(l.value ?? 0).toLocaleString()} rows</dd>
              </div>
            ))}
          </dl>
        </div>
        <div>
          <h3 className="text-sm font-bold text-text">Source freshness</h3>
          <ul className="mt-2 divide-y divide-surface1/50">
            {freshness.map((f) => <Freshness key={f.name} check={f} />)}
          </ul>
        </div>
      </div>
    </section>
  );
}
