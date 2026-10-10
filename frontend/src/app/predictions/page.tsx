'use client';

import { Button } from '@heroui/react';
import { Suspense, useMemo, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { api } from '@/lib/api/client';
import { toCsv } from '@/lib/csv';
import { queryKeys } from '@/lib/api/query-keys';
import { SourceBadge } from '@/components/ui/source-badge';
import { LoadingSkeleton, ErrorMessage, EmptyState } from '@/components/ui/loading';
import { PageHeader } from '@/components/ui/page-header';
import { FootballBadge } from '@/lib/media-utils';
import { Target, Download } from 'lucide-react';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  CartesianGrid,
  Legend,
} from 'recharts';
import { axisProps, gridProps, legendProps, SERIES, tooltipProps } from '@/lib/chart-theme';
import { Panel } from '@/components/ui/panel';
import { Select } from '@/components/ui/select';
import { Stat } from '@/components/ui/stat';
import { Chip } from '@/components/ui/chip';
import { ProbabilityBar } from '@/components/ui/probability-bar';
import { DataTable, TBody, THead, Td, Th } from '@/components/ui/data-table';

const LEAGUE_NAMES: Record<string, string> = {
  E0: 'Premier League', SP1: 'La Liga', D1: 'Bundesliga', I1: 'Serie A', F1: 'Ligue 1',
  N1: 'Eredivisie', P1: 'Primeira Liga', B1: 'Belgian Pro League',
  T1: 'Süper Lig', G1: 'Greek Super League',
};

function PredictionsContent() {
  const [forecastLeague, setForecastLeague] = useState('all');
  const [visibleForecasts, setVisibleForecasts] = useState(30);
  const { data, isLoading, error, refetch } = useQuery({
    queryKey: queryKeys.predictions,
    queryFn: () => api.predictions(),
  });

  const forecasts = useMemo(() => data?.forecasts || [], [data?.forecasts]);
  const forecastLeagues = useMemo(
    () => Array.from(new Set(forecasts.map((row) => row.competition))).sort(),
    [forecasts],
  );
  const filteredForecasts = useMemo(
    () => forecasts
      .filter((row) => forecastLeague === 'all' || row.competition === forecastLeague)
      .sort((a, b) => a.match_date.localeCompare(b.match_date) || a.competition.localeCompare(b.competition)),
    [forecasts, forecastLeague],
  );
  const metrics = data?.metrics || {};

  const accuracy = typeof metrics.accuracy === 'number' ? (metrics.accuracy * 100).toFixed(1) : null;
  const baseline = typeof metrics.baseline_accuracy === 'number' ? (metrics.baseline_accuracy * 100).toFixed(1) : null;
  const logLoss = typeof metrics.log_loss === 'number' ? metrics.log_loss.toFixed(3) : null;
  const rps = typeof metrics.rps === 'number' ? metrics.rps.toFixed(4) : null;
  const ece = typeof metrics.ece === 'number' ? metrics.ece.toFixed(3) : null;
  const validationMatches = typeof metrics.validation_matches === 'number' ? metrics.validation_matches.toLocaleString() : null;
  const shotCoverage = typeof metrics.shot_coverage === 'number' ? (metrics.shot_coverage * 100).toFixed(1) : null;
  const strongThreshold = typeof metrics.high_confidence_threshold === 'number' ? metrics.high_confidence_threshold : 0.75;
  const strongMatches = typeof metrics.high_confidence_matches === 'number' ? metrics.high_confidence_matches : 0;
  const strongAccuracy = typeof metrics.high_confidence_accuracy === 'number' ? metrics.high_confidence_accuracy : null;
  const strongCoverage = typeof metrics.high_confidence_coverage === 'number' ? metrics.high_confidence_coverage : 0;
  const strongLow95 = typeof metrics.high_confidence_low95 === 'number' ? metrics.high_confidence_low95 : null;
  const strongHigh95 = typeof metrics.high_confidence_high95 === 'number' ? metrics.high_confidence_high95 : null;
  const leagueBacktest = Array.isArray(metrics.league_backtest)
    ? [...(metrics.league_backtest as { league: string; matches: number; accuracy: number; log_loss: number }[])]
      .sort((a, b) => b.matches - a.matches)
    : [];
  const outcomeBacktest = Array.isArray(metrics.outcome_backtest)
    ? metrics.outcome_backtest as { outcome: string; matches: number; predicted: number; correct: number; recall: number | null; precision: number | null }[]
    : [];
  const walkForward = Array.isArray(metrics.walk_forward)
    ? metrics.walk_forward as { season: number; matches: number; accuracy: number; log_loss: number; baseline_accuracy: number }[]
    : [];
  const forecastRecord = data?.forecast_record;
  const forecastHistory = data?.forecast_history || [];
  const qualifyingForecasts = forecasts.filter((row) => Math.max(
    row.home_probability, row.draw_probability, row.away_probability,
  ) >= strongThreshold).length;

  const titleRaces = useMemo(() => {
    const leagueOutlooks = data?.league_outlooks || [];
    const grouped = new Map<string, typeof leagueOutlooks>();
    for (const row of leagueOutlooks) {
      const current = grouped.get(row.competition) || [];
      current.push(row);
      grouped.set(row.competition, current);
    }
    return Array.from(grouped, ([competition, rows]) => ({
      competition,
      name: LEAGUE_NAMES[competition] || competition,
      rows: rows.sort((a, b) => b.title_probability - a.title_probability).slice(0, 3),
    }));
  }, [data?.league_outlooks]);

  // Calibration chart data
  const calibrationChartData = useMemo(() => {
    return (data?.calibration || []).map((bin) => ({
      outcome: bin.predicted_outcome === 'Home' ? 'Home Win' : bin.predicted_outcome === 'Away' ? 'Away Win' : 'Draw',
      'Predicted Probability': Number((bin.mean_probability * 100).toFixed(1)),
      'Observed Win Rate': Number((bin.observed_rate * 100).toFixed(1)),
      samples: bin.samples,
    }));
  }, [data?.calibration]);

  // CSV export handler
  const exportCsv = () => {
    const headers = ['Date', 'Competition', 'Home Team', 'Away Team', 'Predicted Result', 'Home %', 'Draw %', 'Away %'];
    const rows = forecasts.map((f) => [
      f.match_date,
      f.competition,
      f.home.name,
      f.away.name,
      f.predicted_result,
      (f.home_probability * 100).toFixed(1),
      (f.draw_probability * 100).toFixed(1),
      (f.away_probability * 100).toFixed(1),
    ]);
    const csvContent = toCsv(headers, rows);
    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.setAttribute('href', url);
    link.setAttribute('download', 'match_forecasts.csv');
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  if (isLoading) return <LoadingSkeleton lines={8} />;
  if (error) {
    return <ErrorMessage title="Failed to load predictions" detail={error.message} retry={() => refetch()} />;
  }

  const pct = (value: number | null | undefined, digits = 1) => (value == null ? '—' : `${(value * 100).toFixed(digits)}%`);
  const pickLabel = (f: typeof forecasts[number]) => f.predicted_result === 'Home' ? `${f.home.name} win` : f.predicted_result === 'Away' ? `${f.away.name} win` : 'Draw';

  return (
    <div className="space-y-4">
      <Panel
        title={data?.model_name || 'Match outcome predictor'}
        description={<>Model ID <span className="font-mono">{data?.model_id || 'n/a'}</span>{data?.validation_cutoff ? ` · cutoff ${data.validation_cutoff}` : ''}</>}
        actions={data?.source && <SourceBadge meta={data.source} />}
      >
        <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 xl:grid-cols-6">
          <Stat inset label="Model accuracy" value={accuracy ? `${accuracy}%` : 'N/A'} />
          <Stat inset label="Baseline accuracy" value={baseline ? `${baseline}%` : 'N/A'} />
          <Stat inset label="Log loss" value={logLoss ?? 'N/A'} />
          <Stat inset label="RPS" value={rps ?? 'N/A'} />
          <Stat inset label="Calibration error (ECE)" value={ece ?? 'N/A'} />
          <Stat inset label="Holdout matches" value={validationMatches ?? 'N/A'} />
        </div>
        <p className="mt-3 text-xs text-subtext0">
          Uses only prior-match Elo, form, rest, shots on target and a market-strength rating learned from earlier matches&apos; prices. {shotCoverage ? `${shotCoverage}% of training results have shot data. ` : ''}Probabilities are calibrated on earlier matches, then scored on a later holdout set; the baseline is learned only from training matches.
        </p>
      </Panel>

      {strongMatches > 0 && strongAccuracy !== null && (
        <Panel bodyClassName="grid gap-4 sm:grid-cols-[10rem_1fr] sm:items-center">
          <div className="border-b border-surface1 pb-3 sm:border-b-0 sm:border-r sm:pb-0 sm:pr-4">
            <p className="text-3xl font-semibold tabular-nums text-text">{(strongAccuracy * 100).toFixed(1)}%</p>
            <p className="text-xs text-subtext0">Observed on strong picks</p>
          </div>
          <div className="space-y-1">
            <h2 className="text-sm font-semibold text-text">A selective tier, not an 80% all-match model</h2>
            <p className="text-xs leading-5 text-subtext0">
              At least {(strongThreshold * 100).toFixed(0)}% predicted for one outcome: {strongMatches} of {validationMatches} holdout matches ({(strongCoverage * 100).toFixed(1)}% coverage).
              {strongLow95 !== null && strongHigh95 !== null && ` The 95% interval is ${(strongLow95 * 100).toFixed(1)}–${(strongHigh95 * 100).toFixed(1)}%.`}
            </p>
            <p className="text-xs font-medium text-accent">{qualifyingForecasts} upcoming fixtures meet this threshold now.</p>
          </div>
        </Panel>
      )}

      {titleRaces.length > 0 && (
        <section className="space-y-3" aria-labelledby="title-outlook-heading">
          <div>
            <h2 id="title-outlook-heading" className="text-sm font-semibold text-text">League Winner Outlook</h2>
            <p className="mt-0.5 text-xs text-subtext0">Title probabilities from current points and smoothed points pace. Early-season estimates stay deliberately conservative.</p>
          </div>
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
            {titleRaces.map((race) => (
              <Panel key={race.competition} as="div">
                <div className="mb-3 flex items-center justify-between gap-3">
                  <div className="min-w-0">
                    <p className="text-xs text-subtext0">{race.competition}</p>
                    <h3 className="truncate text-sm font-semibold text-text">{race.name}</h3>
                  </div>
                  <Chip tone="accent">{((race.rows[0]?.title_probability || 0) * 100).toFixed(1)}%</Chip>
                </div>
                <div className="space-y-3">
                  {race.rows.map((row) => {
                    const probability = row.title_probability * 100;
                    return (
                      <div key={row.team.team_id} className="space-y-1">
                        <div className="flex items-center justify-between gap-2 text-[13px]">
                          <span className="flex min-w-0 items-center gap-2 text-text">
                            <FootballBadge url={row.team.badge_url || row.team.logo_url} name={row.team.name} size={18} />
                            <span className="truncate">{row.team.name}</span>
                          </span>
                          <span className="shrink-0 tabular-nums text-subtext1">{probability.toFixed(1)}%</span>
                        </div>
                        <div className="h-1 overflow-hidden rounded-full bg-surface1">
                          <div className="h-full rounded-full bg-accent" style={{ width: `${Math.max(2, probability)}%` }} />
                        </div>
                        <p className="text-xs tabular-nums text-subtext0">#{row.current_rank} · {row.points} pts · projected {row.projected_points}</p>
                      </div>
                    );
                  })}
                </div>
              </Panel>
            ))}
          </div>
        </section>
      )}

      <Panel
        title={`Upcoming match forecasts (${forecasts.length})`}
        description="Long-range percentages use today’s known form; they cannot account for matches, injuries or transfers that have not happened yet."
        actions={forecasts.length > 0 && <Button size="sm" variant="outline" onPress={exportCsv}><Download className="size-3.5" aria-hidden="true" /> Export all forecasts</Button>}
        bodyClassName="p-0"
      >
        {forecasts.length === 0 ? (
          <EmptyState icon={Target} message="No current match forecasts available." suggestion="Forecasts update when upcoming domestic fixtures are ingested." />
        ) : (
          <>
            <div className="flex flex-wrap items-end justify-between gap-3 border-b border-surface1 px-4 py-3 text-xs text-subtext0">
              <Select label="League" value={forecastLeague} onChange={(value) => { setForecastLeague(value); setVisibleForecasts(30); }}
                options={[{ value: 'all', label: 'All leagues' }, ...forecastLeagues.map((league) => ({ value: league, label: LEAGUE_NAMES[league] || league }))]} className="w-48" />
              <span className="tabular-nums">Showing {Math.min(visibleForecasts, filteredForecasts.length)} of {filteredForecasts.length} forecasts</span>
            </div>
            <ul className="grid grid-cols-1 lg:grid-cols-2">
              {filteredForecasts.slice(0, visibleForecasts).map((f, idx) => {
                const confidence = Math.max(f.home_probability, f.draw_probability, f.away_probability);
                const strong = confidence >= strongThreshold;
                return (
                  <li key={`${f.match_date}_${f.home.team_id}_${f.away.team_id}_${idx}`} className="space-y-2 border-b border-surface1 px-4 py-3 lg:odd:border-r">
                    <div className="flex items-center justify-between text-xs text-subtext0">
                      <span className="tabular-nums">{f.match_date}</span>
                      <Chip>{f.competition}</Chip>
                    </div>
                    <div className="flex items-center justify-between gap-2 text-[13px] font-medium text-text">
                      <span className="flex min-w-0 items-center gap-2"><FootballBadge url={f.home.badge_url} name={f.home.name} size={18} /><span className="truncate">{f.home.name}</span></span>
                      <span className="text-xs text-overlay0">v</span>
                      <span className="flex min-w-0 items-center justify-end gap-2"><span className="truncate">{f.away.name}</span><FootballBadge url={f.away.badge_url} name={f.away.name} size={18} /></span>
                    </div>
                    <ProbabilityBar home={f.home_probability} draw={f.draw_probability} away={f.away_probability} />
                    <div className="flex items-center justify-between text-xs">
                      <span className="text-subtext0">Pick: <span className="font-medium text-text">{pickLabel(f)}</span></span>
                      <span className={strong ? 'font-medium text-accent' : 'text-subtext0'}>
                        {strong ? 'High-confidence tier' : confidence >= 0.6 ? 'Moderate lean' : 'Open match'} · {(confidence * 100).toFixed(1)}%
                      </span>
                    </div>
                  </li>
                );
              })}
            </ul>
            {visibleForecasts < filteredForecasts.length && (
              <div className="p-3">
                <Button variant="outline" size="sm" onPress={() => setVisibleForecasts((count) => count + 30)}>Show 30 more forecasts</Button>
              </div>
            )}
          </>
        )}
      </Panel>

      {calibrationChartData.length > 0 && (
        <Panel title="Reliability calibration" description="Mean forecast probability against the observed rate per outcome in the holdout matches">
          <div className="h-60 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={calibrationChartData} margin={{ top: 4, right: 8, left: -16, bottom: 0 }}>
                <CartesianGrid {...gridProps} />
                <XAxis dataKey="outcome" {...axisProps} />
                <YAxis {...axisProps} unit="%" />
                <Tooltip {...tooltipProps} formatter={(val) => [`${val}%`]} />
                <Legend {...legendProps} />
                <Bar dataKey="Predicted Probability" fill={SERIES[0]} radius={[3, 3, 0, 0]} maxBarSize={36} />
                <Bar dataKey="Observed Win Rate" fill={SERIES[3]} radius={[3, 3, 0, 0]} maxBarSize={36} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </Panel>
      )}

      {leagueBacktest.length > 0 && (
        <Panel title="Holdout by league" description="The same later test period, split by competition. Small samples are less reliable." bodyClassName="p-0">
          <DataTable minWidth={420} caption="Holdout by league">
            <THead><tr><Th>League</Th><Th align="right">Matches</Th><Th align="right">Accuracy</Th><Th align="right">Log loss</Th></tr></THead>
            <TBody>
              {leagueBacktest.map((row) => (
                <tr key={row.league}>
                  <Td className="font-medium">{LEAGUE_NAMES[row.league] || row.league}</Td>
                  <Td align="right" className="text-subtext1">{row.matches}</Td>
                  <Td align="right">{pct(row.accuracy)}</Td>
                  <Td align="right" className="text-subtext1">{row.log_loss.toFixed(3)}</Td>
                </tr>
              ))}
            </TBody>
          </DataTable>
        </Panel>
      )}

      {(outcomeBacktest.length > 0 || walkForward.length > 0) && (
        <div className="grid gap-4 xl:grid-cols-2">
          {outcomeBacktest.length > 0 && (
            <Panel title="Home, draw and away audit" description="Recall: how often each real outcome was found. Precision: how often that prediction was right." bodyClassName="p-0">
              <DataTable minWidth={380} caption="Outcome audit">
                <THead><tr><Th>Outcome</Th><Th align="right">Actual</Th><Th align="right">Predicted</Th><Th align="right">Recall</Th><Th align="right">Precision</Th></tr></THead>
                <TBody>
                  {outcomeBacktest.map((row) => (
                    <tr key={row.outcome}>
                      <Td className="font-medium">{row.outcome}</Td>
                      <Td align="right" className="text-subtext1">{row.matches}</Td>
                      <Td align="right" className="text-subtext1">{row.predicted}</Td>
                      <Td align="right">{pct(row.recall)}</Td>
                      <Td align="right">{pct(row.precision)}</Td>
                    </tr>
                  ))}
                </TBody>
              </DataTable>
            </Panel>
          )}
          {walkForward.length > 0 && (
            <Panel title="Season-by-season walk-forward" description="Each season is scored using only earlier seasons for fitting and calibration." bodyClassName="p-0">
              <DataTable minWidth={360} caption="Walk-forward seasons">
                <THead><tr><Th>Season</Th><Th align="right">Games</Th><Th align="right">Accuracy</Th><Th align="right">Baseline</Th><Th align="right">Log loss</Th></tr></THead>
                <TBody>
                  {walkForward.map((row) => (
                    <tr key={row.season}>
                      <Td className="font-medium">{row.season}/{String(row.season + 1).slice(-2)}</Td>
                      <Td align="right" className="text-subtext1">{row.matches}</Td>
                      <Td align="right">{pct(row.accuracy)}</Td>
                      <Td align="right" className="text-subtext1">{pct(row.baseline_accuracy)}</Td>
                      <Td align="right" className="text-subtext1">{row.log_loss.toFixed(3)}</Td>
                    </tr>
                  ))}
                </TBody>
              </DataTable>
            </Panel>
          )}
        </div>
      )}

      <Panel title="Published forecast record" description="Forecasts are kept as issued and matched with results after refresh. Re-forecasts for the same match are separate records.">
        <p className="text-sm font-medium text-text">
          {forecastRecord?.resolved ? `${forecastRecord.correct ?? 0} correct of ${forecastRecord.resolved} resolved (${((forecastRecord.accuracy ?? 0) * 100).toFixed(1)}%)` : 'No published forecasts resolved yet'}
          <span className="ml-2 text-xs font-normal text-subtext0">· {forecastRecord?.issued ?? 0} issued</span>
        </p>
        <p className="mt-1 text-xs text-subtext0">
          {forecastRecord?.rps != null
            ? `Live RPS ${forecastRecord.rps.toFixed(4)} on ${forecastRecord.matches_scored} matches (last forecast before kick-off)${forecastRecord.walk_forward_rps != null ? ` vs ${forecastRecord.walk_forward_rps.toFixed(4)} walk-forward; lower is better` : ''}.`
            : 'Live RPS appears once forecast matches have results.'}
        </p>
        {forecastHistory.length > 0 && (
          <div className="mt-3 overflow-hidden rounded-lg border border-surface1">
            <DataTable minWidth={500} caption="Recent journal entries">
              <THead><tr><Th>Issued</Th><Th>Fixture</Th><Th>Pick</Th><Th>Result</Th></tr></THead>
              <TBody>
                {forecastHistory.map((row) => (
                  <tr key={`${row.model_id}-${row.competition}-${row.match_date}-${row.home.team_id}-${row.away.team_id}`}>
                    <Td className="text-subtext0">{row.issued_at.slice(0, 10)}</Td>
                    <Td>{row.home.name} – {row.away.name}</Td>
                    <Td className="text-subtext1">{row.predicted_result}</Td>
                    <Td>{row.actual_result ? <Chip tone={row.actual_result === row.predicted_result ? 'positive' : 'negative'}>{row.actual_result}</Chip> : <span className="text-subtext0">Pending</span>}</Td>
                  </tr>
                ))}
              </TBody>
            </DataTable>
          </div>
        )}
      </Panel>
    </div>
  );
}

export default function PredictionsPage() {
  return (
    <div className="space-y-5">
      <PageHeader icon={Target} eyebrow="Model intelligence" title="Predictions & Model Card" description="Review calibrated match probabilities, chronological holdout evidence, and every supported league's title outlook." />

      <Suspense fallback={<LoadingSkeleton lines={8} />}>
        <PredictionsContent />
      </Suspense>
    </div>
  );
}
