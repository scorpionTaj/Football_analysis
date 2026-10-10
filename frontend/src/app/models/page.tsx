'use client';

import { useMemo, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
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
import { axisProps, gridProps, legendProps, OUTCOME, SERIES, tooltipProps } from '@/lib/chart-theme';
import { Panel } from '@/components/ui/panel';
import { Chip } from '@/components/ui/chip';
import { DataTable, SortTh, TBody, THead, Td } from '@/components/ui/data-table';
import { useTableView } from '@/lib/hooks/use-table-view';

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
        <h2 id="ladder-title" className="text-sm font-semibold text-text">How much of the bookmaker&rsquo;s edge each model recovers</h2>
        <p className="mt-1 max-w-3xl text-pretty text-xs text-subtext0">
          0% is guessing each league&rsquo;s base rates (RPS {base.rps.toFixed(4)}); 100% is the closing betting line
          (RPS {market.rps.toFixed(4)}), the sharpest public forecast. Scored on {base.matches.toLocaleString()} top-flight
          matches the models never saw.
        </p>
      </figcaption>
      <ol className="mt-5 space-y-2.5">
        {placed.map((run) => (
          <li key={run.model} className="grid grid-cols-[1fr_auto] items-center gap-x-3 gap-y-1.5 sm:grid-cols-[minmax(9rem,16rem)_1fr_4rem] sm:gap-4">
            <span className="min-w-0 text-[13px] font-medium text-text">
              {name(run.model)}
              {run.model === champion && <Chip tone="accent" className="ml-2">Champion</Chip>}
              {!run.independent && <span className="ml-2 text-xs text-subtext0">uses odds</span>}
            </span>
            <span className="relative col-span-2 row-start-2 h-1.5 rounded-full bg-surface1 sm:col-span-1 sm:row-start-auto" title={`${name(run.model)}: ${pct(run.skill)} of the closing line's skill`}>
              <span
                className={`absolute inset-y-0 left-0 rounded-full ${run.model === champion ? 'bg-accent' : run.independent ? 'bg-overlay0' : 'bg-surface2'}`}
                style={{ width: x(run.skill) }}
              />
            </span>
            <span className="text-right text-[13px] font-semibold tabular-nums text-text">{pct(run.skill)}</span>
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
        <div key={row.key} className="rounded-xl border border-surface1 bg-surface0 px-4 py-3">
          <dt className="text-xs font-medium text-subtext0">{row.label}</dt>
          <dd className="mt-1 text-2xl font-semibold tracking-tight tabular-nums text-text">{row.value}</dd>
          <dd className={`mt-1.5 flex items-center gap-1.5 text-xs font-medium ${row.ok ? 'text-positive' : 'text-warning'}`}>
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
        <CartesianGrid {...gridProps} />
        <XAxis dataKey="season" {...axisProps} />
        <YAxis {...axisProps} domain={['auto', 'auto']} width={52}
               tickFormatter={(v: number) => v.toFixed(3)} />
        <Tooltip {...tooltipProps} formatter={(v, key) => [Number(v).toFixed(4), name(String(key))]} />
        <Legend {...legendProps} formatter={(key: string) => <span className="text-xs text-subtext0">{name(key)}</span>} />
        {[...shown].reverse().map((r) => (
          <Line key={r.model} dataKey={r.model} stroke={SERIES[shown.indexOf(r)]} strokeWidth={r.model === champion ? 2.5 : 1.5} dot={{ r: 3 }} activeDot={{ r: 5 }}
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
        <CartesianGrid {...gridProps} vertical />
        <XAxis type="number" dataKey="predicted" domain={[0, 0.9]} {...axisProps}
               tickFormatter={(v: number) => pct(v, 0)} name="Predicted" />
        <YAxis type="number" dataKey="observed" domain={[0, 0.9]} {...axisProps}
               tickFormatter={(v: number) => pct(v, 0)} name="Observed" width={52} />
        <ZAxis type="number" dataKey="n" range={[40, 160]} name="Matches" />
        <Tooltip {...tooltipProps} formatter={(v, key) => (key === 'Matches' ? Number(v).toLocaleString() : pct(Number(v)))} />
        <Legend {...legendProps} formatter={(key: string) => <span className="text-xs text-subtext0">{key === 'Draw' ? 'Draw' : `${key} win`}</span>} />
        <Scatter name="Perfect calibration" data={[{ predicted: 0, observed: 0, n: 1 }, { predicted: 0.9, observed: 0.9, n: 1 }]}
                 line={{ stroke: 'var(--chart-axis)', strokeDasharray: '4 4' }} shape={() => <g />} legendType="none" isAnimationActive={false} />
        {outcomes.map((outcome, i) => (
          <Scatter key={outcome} name={outcome} data={run.calibration.filter((p) => p.outcome === outcome)}
                   fill={[OUTCOME.home, OUTCOME.draw, OUTCOME.away][i]} stroke="var(--surface0)" strokeWidth={1.5} isAnimationActive={false} />
        ))}
      </ScatterChart>
    </ResponsiveContainer>
  );
}

function Leaderboard({ runs }: { runs: ModelRun[] }) {
  const table = useTableView(runs, {
    columns: {
      model: (r) => name(r.model), rps: (r) => r.rps, logLoss: (r) => r.log_loss, brier: (r) => r.brier,
      accuracy: (r) => r.accuracy, ece: (r) => r.ece,
    },
    initial: { key: 'rps', dir: 'asc' },
  });
  return (
    <DataTable minWidth={640} caption="All candidate models, walk-forward scores">
      <THead>
        <tr>
          <SortTh {...table.sortProps('model')}>Model</SortTh>
          <SortTh align="right" {...table.sortProps('rps')}>RPS</SortTh>
          <SortTh align="right" {...table.sortProps('logLoss')}>Log loss</SortTh>
          <SortTh align="right" {...table.sortProps('brier')}>Brier</SortTh>
          <SortTh align="right" {...table.sortProps('accuracy')}>Accuracy</SortTh>
          <SortTh align="right" {...table.sortProps('ece')}>ECE</SortTh>
        </tr>
      </THead>
      <TBody>
        {table.rows.map((run) => (
          <tr key={run.model}>
            <th scope="row" className="h-9 px-3 text-left font-medium text-text">
              {name(run.model)}
              {run.is_champion && <Chip tone="accent" className="ml-2">Champion</Chip>}
            </th>
            <Td align="right" className="text-subtext1">{run.rps.toFixed(4)}</Td>
            <Td align="right" className="text-subtext1">{run.log_loss.toFixed(4)}</Td>
            <Td align="right" className="text-subtext1">{run.brier.toFixed(4)}</Td>
            <Td align="right" className="text-subtext1">{pct(run.accuracy)}</Td>
            <Td align="right" className="text-subtext1">{run.ece.toFixed(4)}</Td>
          </tr>
        ))}
      </TBody>
    </DataTable>
  );
}

export default function ModelLabPage() {
  const [showTable, setShowTable] = useState(false);
  const { data, isLoading, error, refetch } = useQuery({ queryKey: queryKeys.models, queryFn: () => api.models() });
  const champion = data?.runs.find((r) => r.is_champion);

  return (
    <div className="space-y-5">
      <PageHeader
        icon={FlaskConical}
        eyebrow="Model lab"
        title="Which forecast model wins, and by how much"
        description="Nine candidates trained on 20 seasons across 15 leagues, then scored season by season on matches they had not seen."
        action={data ? <SourceBadge meta={data.source} /> : undefined}
      />

      {isLoading && <Panel><LoadingSkeleton lines={8} /></Panel>}
      {error && <ErrorMessage title="Model results could not be loaded" detail={String(error)} retry={() => refetch()} />}
      {data && !data.runs.length && (
        <EmptyState icon={FlaskConical} message="No model runs yet" suggestion="Run football-train-models (or a full refresh) to build the leaderboard." />
      )}

      {data && champion && (
        <>
          <Panel>
            <SkillLadder runs={data.runs} champion={data.champion} />
          </Panel>

          <section aria-labelledby="targets-title" className="space-y-3">
            <h2 id="targets-title" className="text-sm font-semibold text-text">Champion against its acceptance targets</h2>
            <Targets run={champion} targets={data.targets} />
          </section>

          <div className="grid gap-4 xl:grid-cols-2">
            <Panel title="Ranked probability score by season" description="Lower is better. Each season is predicted by a model trained only on earlier seasons.">
              <SeasonChart runs={data.runs} champion={champion.model} />
            </Panel>
            <Panel title="Does 60% mean 60%?" description={`${name(champion.model)}: predicted probability against how often the outcome happened. Points on the dashed line are perfectly calibrated.`}>
              <Reliability run={champion} />
            </Panel>
          </div>

          <Panel
            title="All models"
            actions={<button type="button" onClick={() => setShowTable((v) => !v)} aria-expanded={showTable}
              className="h-8 rounded-lg border border-surface1 px-3 text-xs font-medium text-text transition-colors hover:bg-surface1">
              {showTable ? 'Hide scores' : 'Show scores'}
            </button>}
            bodyClassName={showTable ? 'p-0' : 'hidden'}
          >
            {showTable && <Leaderboard runs={data.runs} />}
          </Panel>
        </>
      )}
    </div>
  );
}
