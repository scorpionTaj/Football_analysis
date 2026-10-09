'use client';

import { useMemo, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Card } from '@heroui/react';
import { CheckCircle2, CircleAlert, FlaskConical } from 'lucide-react';
import {
  CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Scatter, ScatterChart, Tooltip, XAxis, YAxis, ZAxis,
} from 'recharts';
import { api } from '@/lib/api/client';
import { queryKeys } from '@/lib/api/query-keys';
import type { ModelRun } from '@/lib/api/types';
import { PageHeader } from '@/components/ui/page-header';
import { SourceBadge } from '@/components/ui/source-badge';
import { EmptyState, ErrorMessage, LoadingSkeleton } from '@/components/ui/loading';
import { tooltipProps } from '@/lib/chart-theme';

const NAMES: Record<string, string> = {
  prevalence_baseline: 'Base-rate guess',
  elo_logit: 'Elo only',
  logreg: 'Logistic regression',
  lightgbm: 'LightGBM',
  poisson_dixon_coles: 'Poisson + Dixon-Coles',
  ensemble: 'Ensemble',
  stacked: 'Stacked (meta-learner)',
  market_blend: 'Model + opening odds',
  market_closing: 'Bookmaker closing line',
};
const name = (model: string) => NAMES[model] ?? model.replaceAll('_', ' ');
const SERIES = ['var(--series-1)', 'var(--series-2)', 'var(--series-3)', 'var(--series-4)'];
const pct = (v: number, digits = 1) => `${(v * 100).toFixed(digits)}%`;
const season = (s: number) => `${s}/${String(s + 1).slice(-2)}`;

/** Each model's position between the base-rate guess (0) and the closing line (1), by RPS. */
function SkillLadder({ runs, champion }: { runs: ModelRun[]; champion: string | null }) {
  const base = runs.find((r) => r.model === 'prevalence_baseline');
  const market = runs.find((r) => r.model === 'market_closing');
  if (!base || !market) return null;
  const span = base.rps - market.rps;
  const placed = runs
    .filter((r) => r.model !== 'prevalence_baseline' && r.model !== 'market_closing')
    .map((r) => ({ ...r, skill: (base.rps - r.rps) / span }))
    .sort((a, b) => b.skill - a.skill);
  const min = Math.min(0.85, ...placed.map((r) => r.skill)) - 0.03;
  const x = (skill: number) => `${((skill - min) / (1 - min)) * 100}%`;

  return (
    <figure aria-labelledby="ladder-title">
      <figcaption>
        <h2 id="ladder-title" className="text-lg font-bold text-text">How much of the bookmaker&rsquo;s edge each model recovers</h2>
        <p className="mt-1 max-w-3xl text-pretty text-sm text-subtext0">
          0% is guessing each league&rsquo;s base rates (RPS {base.rps.toFixed(4)}); 100% is the closing betting line
          (RPS {market.rps.toFixed(4)}), the sharpest public forecast. Scored on {base.matches.toLocaleString()} top-flight
          matches the models never saw.
        </p>
      </figcaption>
      <ol className="mt-6 space-y-3">
        {placed.map((run) => (
          <li key={run.model} className="grid grid-cols-[1fr_auto] items-center gap-x-3 gap-y-1.5 sm:grid-cols-[minmax(9rem,16rem)_1fr_4rem] sm:gap-4">
            <span className="min-w-0 text-sm font-semibold text-text">
              {name(run.model)}
              {run.model === champion && <span className="ml-2 rounded-md bg-blue/15 px-1.5 py-0.5 text-[11px] font-bold text-blue">Champion</span>}
              {!run.independent && <span className="ml-2 text-[11px] font-medium text-subtext0">uses odds</span>}
            </span>
            <span className="relative col-span-2 row-start-2 h-2.5 rounded-full bg-surface1/70 sm:col-span-1 sm:row-start-auto" title={`${name(run.model)}: ${pct(run.skill)} of the closing line's skill`}>
              <span
                className={`absolute inset-y-0 left-0 rounded-full ${run.model === champion ? 'bg-blue' : run.independent ? 'bg-overlay0' : 'bg-surface2'}`}
                style={{ width: x(run.skill) }}
              />
            </span>
            <span className="text-right text-sm font-bold tabular-nums text-text">{pct(run.skill)}</span>
          </li>
        ))}
      </ol>
      <p className="mt-3 text-xs text-subtext0">Axis starts at {pct(min, 0)} so differences between strong models stay visible.</p>
    </figure>
  );
}

function Targets({ run, targets }: { run: ModelRun; targets: Record<string, number> }) {
  const rows = [
    { key: 'log_loss', label: 'Log loss', value: run.log_loss.toFixed(4), ok: run.log_loss <= targets.log_loss, goal: `≤ ${targets.log_loss}` },
    { key: 'rps', label: 'Ranked probability score', value: run.rps.toFixed(4), ok: run.rps <= targets.rps, goal: `≤ ${targets.rps}` },
    { key: 'accuracy', label: 'Accuracy', value: pct(run.accuracy), ok: run.accuracy >= targets.accuracy, goal: `≥ ${pct(targets.accuracy)}` },
    { key: 'ece', label: 'Calibration error', value: run.ece.toFixed(4), ok: run.ece <= targets.ece, goal: `≤ ${targets.ece}` },
  ];
  return (
    <dl className="grid grid-cols-2 gap-3 lg:grid-cols-4">
      {rows.map((row) => (
        <div key={row.key} className="rounded-2xl border border-surface1/70 bg-surface0/60 p-4">
          <dt className="text-xs font-semibold text-subtext0">{row.label}</dt>
          <dd className="mt-1 text-2xl font-black tabular-nums text-text">{row.value}</dd>
          <dd className={`mt-2 flex items-center gap-1.5 text-xs font-semibold ${row.ok ? 'text-green' : 'text-yellow'}`}>
            {row.ok ? <CheckCircle2 className="size-3.5" aria-hidden="true" /> : <CircleAlert className="size-3.5" aria-hidden="true" />}
            {row.ok ? 'Target met' : 'Below target'} · goal {row.goal}
          </dd>
        </div>
      ))}
    </dl>
  );
}

function SeasonChart({ runs, champion }: { runs: ModelRun[]; champion: string }) {
  // Champion vs the simplest rating model vs the market: near-identical candidates would overlap.
  const shown = [champion, 'elo_logit', 'market_closing'].filter((m, i, a) => a.indexOf(m) === i)
    .map((m) => runs.find((r) => r.model === m)).filter(Boolean) as ModelRun[];
  const data = useMemo(() => {
    const seasons = Array.from(new Set(shown.flatMap((r) => r.seasons.map((s) => s.season)))).sort();
    return seasons.map((s) => ({
      season: season(s),
      ...Object.fromEntries(shown.map((r) => [r.model, r.seasons.find((x) => x.season === s)?.rps ?? null])),
    }));
  }, [shown]);
  return (
    <ResponsiveContainer width="100%" height={280}>
      <LineChart data={data} margin={{ top: 8, right: 16, bottom: 4, left: 0 }}>
        <CartesianGrid stroke="var(--surface1)" strokeOpacity={0.5} vertical={false} />
        <XAxis dataKey="season" stroke="var(--overlay0)" fontSize={12} tickLine={false} />
        <YAxis stroke="var(--overlay0)" fontSize={12} tickLine={false} domain={['auto', 'auto']} width={52}
               tickFormatter={(v: number) => v.toFixed(3)} />
        <Tooltip {...tooltipProps}
                 labelStyle={{ color: 'var(--text)' }} itemStyle={{ color: 'var(--subtext1)' }}
                 formatter={(v, key) => [Number(v).toFixed(4), name(String(key))]} />
        <Legend formatter={(key: string) => <span className="text-xs text-subtext1">{name(key)}</span>} />
        {[...shown].reverse().map((r) => (
          <Line key={r.model} dataKey={r.model} stroke={SERIES[shown.indexOf(r)]} strokeWidth={r.model === champion ? 3 : 2} dot={{ r: 4 }} activeDot={{ r: 6 }}
                isAnimationActive={false} />
        ))}
      </LineChart>
    </ResponsiveContainer>
  );
}

function Reliability({ run }: { run: ModelRun }) {
  const outcomes = ['Home', 'Draw', 'Away'] as const;
  return (
    <ResponsiveContainer width="100%" height={280}>
      <ScatterChart margin={{ top: 8, right: 16, bottom: 4, left: 0 }}>
        <CartesianGrid stroke="var(--surface1)" strokeOpacity={0.5} />
        <XAxis type="number" dataKey="predicted" domain={[0, 0.9]} stroke="var(--overlay0)" fontSize={12}
               tickFormatter={(v: number) => pct(v, 0)} name="Predicted" />
        <YAxis type="number" dataKey="observed" domain={[0, 0.9]} stroke="var(--overlay0)" fontSize={12}
               tickFormatter={(v: number) => pct(v, 0)} name="Observed" width={52} />
        <ZAxis type="number" dataKey="n" range={[40, 160]} name="Matches" />
        <Tooltip {...tooltipProps}
                 itemStyle={{ color: 'var(--subtext1)' }}
                 formatter={(v, key) => (key === 'Matches' ? Number(v).toLocaleString() : pct(Number(v)))} />
        <Legend formatter={(key: string) => <span className="text-xs text-subtext1">{key === 'Draw' ? 'Draw' : `${key} win`}</span>} />
        <Scatter name="Perfect calibration" data={[{ predicted: 0, observed: 0, n: 1 }, { predicted: 0.9, observed: 0.9, n: 1 }]}
                 line={{ stroke: 'var(--overlay0)', strokeDasharray: '4 4' }} shape={() => <g />} legendType="none" isAnimationActive={false} />
        {outcomes.map((outcome, i) => (
          <Scatter key={outcome} name={outcome} data={run.calibration.filter((p) => p.outcome === outcome)}
                   fill={SERIES[i]} stroke="var(--base)" strokeWidth={2} isAnimationActive={false} />
        ))}
      </ScatterChart>
    </ResponsiveContainer>
  );
}

function Leaderboard({ runs }: { runs: ModelRun[] }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[640px] text-sm">
        <caption className="sr-only">All candidate models, walk-forward scores</caption>
        <thead>
          <tr className="border-b border-surface1 text-left text-xs text-subtext0">
            <th scope="col" className="py-2 font-semibold">Model</th>
            {['RPS', 'Log loss', 'Brier', 'Accuracy', 'ECE'].map((h) => (
              <th key={h} scope="col" className="py-2 text-right font-semibold">{h}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {runs.map((run) => (
            <tr key={run.model} className="border-b border-surface1/40 last:border-0">
              <th scope="row" className="py-2 text-left font-semibold text-text">
                {name(run.model)}
                {run.is_champion && <span className="ml-2 text-[11px] font-bold text-blue">Champion</span>}
              </th>
              <td className="py-2 text-right tabular-nums text-subtext1">{run.rps.toFixed(4)}</td>
              <td className="py-2 text-right tabular-nums text-subtext1">{run.log_loss.toFixed(4)}</td>
              <td className="py-2 text-right tabular-nums text-subtext1">{run.brier.toFixed(4)}</td>
              <td className="py-2 text-right tabular-nums text-subtext1">{pct(run.accuracy)}</td>
              <td className="py-2 text-right tabular-nums text-subtext1">{run.ece.toFixed(4)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default function ModelLabPage() {
  const [showTable, setShowTable] = useState(false);
  const { data, isLoading, error, refetch } = useQuery({ queryKey: queryKeys.models, queryFn: () => api.models() });
  const champion = data?.runs.find((r) => r.is_champion);

  return (
    <div className="space-y-6">
      <PageHeader
        icon={FlaskConical}
        eyebrow="Model lab"
        title="Which forecast model wins, and by how much"
        description="Eight candidates trained on 20 seasons across 15 leagues, then scored season by season on matches they had not seen."
        action={data ? <SourceBadge meta={data.source} /> : undefined}
      />

      {isLoading && <Card className="p-6"><LoadingSkeleton lines={8} /></Card>}
      {error && <ErrorMessage title="Model results could not be loaded" detail={String(error)} retry={() => refetch()} />}
      {data && !data.runs.length && (
        <EmptyState icon="🧪" message="No model runs yet" suggestion="Run football-train-models (or a full refresh) to build the leaderboard." />
      )}

      {data && champion && (
        <>
          <Card className="border border-surface1/70 bg-surface0/60 p-5 sm:p-6">
            <SkillLadder runs={data.runs} champion={data.champion} />
          </Card>

          <section aria-labelledby="targets-title" className="space-y-3">
            <h2 id="targets-title" className="text-lg font-bold text-text">Champion against its acceptance targets</h2>
            <Targets run={champion} targets={data.targets} />
          </section>

          <div className="grid gap-6 xl:grid-cols-2">
            <Card className="border border-surface1/70 bg-surface0/60 p-5">
              <h2 className="text-base font-bold text-text">Ranked probability score by season</h2>
              <p className="mt-1 text-sm text-subtext0">Lower is better. Each season is predicted by a model trained only on earlier seasons.</p>
              <div className="mt-4"><SeasonChart runs={data.runs} champion={champion.model} /></div>
            </Card>
            <Card className="border border-surface1/70 bg-surface0/60 p-5">
              <h2 className="text-base font-bold text-text">Does 60% mean 60%?</h2>
              <p className="mt-1 text-sm text-subtext0">
                {name(champion.model)}: predicted probability against how often the outcome happened. Points on the dashed line are perfectly calibrated.
              </p>
              <div className="mt-4"><Reliability run={champion} /></div>
            </Card>
          </div>

          <Card className="border border-surface1/70 bg-surface0/60 p-5">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <h2 className="text-base font-bold text-text">All models</h2>
              <button type="button" onClick={() => setShowTable((v) => !v)} aria-expanded={showTable}
                      className="rounded-lg bg-surface1 px-3 py-1.5 text-sm font-semibold text-text transition-colors hover:bg-surface2 focus-visible:outline focus-visible:outline-2 focus-visible:outline-blue">
                {showTable ? 'Hide scores' : 'Show scores'}
              </button>
            </div>
            {showTable && <div className="mt-4"><Leaderboard runs={data.runs} /></div>}
          </Card>
        </>
      )}
    </div>
  );
}
