'use client';

import { Card, Button } from '@heroui/react';
import { Suspense, useMemo, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { api } from '@/lib/api/client';
import { toCsv } from '@/lib/csv';
import { queryKeys } from '@/lib/api/query-keys';
import { SourceBadge } from '@/components/ui/source-badge';
import { LoadingSkeleton, ErrorMessage, EmptyState } from '@/components/ui/loading';
import { PageHeader } from '@/components/ui/page-header';
import { FootballBadge } from '@/lib/media-utils';
import { Cpu, Target, CheckCircle2, Download, Calendar, BarChart2, Trophy } from 'lucide-react';
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
  const temperature = typeof metrics.temperature === 'number' ? metrics.temperature.toFixed(2) : null;
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

  return (
    <div className="space-y-6">
      {/* Model Card Header */}
      <Card className="rounded-xl border border-surface1 bg-surface0 p-5 space-y-3 shadow-sm">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-surface1 pb-3">
          <div className="flex items-center gap-3">
            <div className="p-2.5 rounded-lg bg-blue/10 text-blue">
              <Cpu className="h-5 w-5" />
            </div>
            <div>
              <h2 className="text-base font-bold text-text">{data?.model_name || 'Match Outcome Predictor'}</h2>
              <p className="text-xs text-subtext0 mt-0.5">
                Model ID: <span className="font-mono text-subtext1">{data?.model_id || 'n/a'}</span>
                {data?.validation_cutoff && (
                  <span className="ml-2">· Cutoff: <span className="text-subtext1">{data.validation_cutoff}</span></span>
                )}
              </p>
            </div>
          </div>
          {data?.source && <SourceBadge meta={data.source} />}
        </div>

        {/* Model Metrics */}
        <div className="grid grid-cols-2 sm:grid-cols-3 xl:grid-cols-6 gap-3 pt-1">
          <div className="rounded-lg bg-mantle p-3 border border-surface1">
            <p className="text-xs uppercase text-subtext0 font-medium">Model Accuracy</p>
            <p className="text-xl font-bold text-green mt-1">{accuracy ? `${accuracy}%` : 'N/A'}</p>
          </div>
          <div className="rounded-lg bg-mantle p-3 border border-surface1">
            <p className="text-xs uppercase text-subtext0 font-medium">Baseline Accuracy</p>
            <p className="text-xl font-bold text-subtext1 mt-1">{baseline ? `${baseline}%` : 'N/A'}</p>
          </div>
          <div className="rounded-lg bg-mantle p-3 border border-surface1">
            <p className="text-xs uppercase text-subtext0 font-medium">Log Loss</p>
            <p className="text-xl font-bold text-blue mt-1">{logLoss ?? 'N/A'}</p>
          </div>
          <div className="rounded-lg bg-mantle p-3 border border-surface1">
            <p className="text-xs uppercase text-subtext0 font-medium">Active Forecasts</p>
            <p className="text-xl font-bold text-peach mt-1">{forecasts.length}</p>
          </div>
          <div className="rounded-lg bg-mantle p-3 border border-surface1">
            <p className="text-xs uppercase text-subtext0 font-medium">Calibration</p>
            <p className="text-xl font-bold text-mauve mt-1">{temperature ? `${temperature}×` : 'N/A'}</p>
          </div>
          <div className="rounded-lg bg-mantle p-3 border border-surface1">
            <p className="text-xs uppercase text-subtext0 font-medium">Holdout Matches</p>
            <p className="text-xl font-bold text-text mt-1">{validationMatches ?? 'N/A'}</p>
          </div>
        </div>
        <p className="text-xs text-subtext0">
          Uses only prior-match Elo, form, rest and shots on target. {shotCoverage ? `${shotCoverage}% of training results have shot data. ` : ''}Probabilities are calibrated on earlier matches, then scored on a later holdout set; the baseline is learned only from training matches.
        </p>
      </Card>

      {strongMatches > 0 && strongAccuracy !== null && (
        <Card className="grid gap-4 rounded-xl border border-teal/40 bg-teal/5 p-5 sm:grid-cols-[11rem_1fr] sm:items-center">
          <div className="border-b border-teal/30 pb-4 sm:border-b-0 sm:border-r sm:pb-0 sm:pr-5">
            <p className="text-3xl font-black tabular-nums text-teal">{(strongAccuracy * 100).toFixed(1)}%</p>
            <p className="text-xs font-semibold text-text">Observed on strong picks</p>
          </div>
          <div className="space-y-1.5">
            <h2 className="text-sm font-bold text-text">A selective tier, not an 80% all-match model</h2>
            <p className="text-xs leading-5 text-subtext1">
              At least {(strongThreshold * 100).toFixed(0)}% predicted for one outcome: {strongMatches} of {validationMatches} holdout matches ({(strongCoverage * 100).toFixed(1)}% coverage).
              {strongLow95 !== null && strongHigh95 !== null && ` The 95% interval is ${(strongLow95 * 100).toFixed(1)}–${(strongHigh95 * 100).toFixed(1)}%.`}
            </p>
            <p className="text-xs font-semibold text-teal">{qualifyingForecasts} upcoming fixtures meet this threshold now.</p>
          </div>
        </Card>
      )}

      {titleRaces.length > 0 && (
        <section className="space-y-4" aria-labelledby="title-outlook-heading">
          <div>
            <div className="flex items-center gap-2">
              <Trophy className="h-4 w-4 text-yellow" />
              <h2 id="title-outlook-heading" className="text-base font-semibold text-text">League Winner Outlook</h2>
            </div>
            <p className="mt-1 text-xs text-subtext0">
              Data-driven title probabilities from current points and smoothed points pace. Early-season estimates remain deliberately conservative.
            </p>
          </div>
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
            {titleRaces.map((race) => (
              <Card key={race.competition} className="rounded-xl border border-surface1 bg-surface0 p-4 shadow-sm">
                <div className="mb-3 flex items-center justify-between gap-3">
                  <div>
                    <p className="text-xs font-bold uppercase tracking-wide text-subtext0">{race.competition}</p>
                    <h3 className="text-sm font-bold text-text">{race.name}</h3>
                  </div>
                  <span className="rounded-full bg-yellow/10 px-2 py-1 text-xs font-bold text-yellow">
                    {((race.rows[0]?.title_probability || 0) * 100).toFixed(1)}%
                  </span>
                </div>
                <div className="space-y-3">
                  {race.rows.map((row) => {
                    const probability = row.title_probability * 100;
                    return (
                      <div key={row.team.team_id} className="space-y-1.5">
                        <div className="flex items-center justify-between gap-2 text-xs">
                          <span className="flex min-w-0 items-center gap-2 font-semibold text-text">
                            <FootballBadge url={row.team.badge_url || row.team.logo_url} name={row.team.name} size={22} />
                            <span className="truncate">{row.team.name}</span>
                          </span>
                          <span className="shrink-0 font-mono text-subtext1">{probability.toFixed(1)}%</span>
                        </div>
                        <div className="h-1.5 overflow-hidden rounded-full bg-mantle">
                          <div className="h-full rounded-full bg-gradient-to-r from-yellow to-peach" style={{ width: `${Math.max(2, probability)}%` }} />
                        </div>
                        <p className="text-[10px] text-subtext0">#{row.current_rank} · {row.points} pts · projected {row.projected_points}</p>
                      </div>
                    );
                  })}
                </div>
              </Card>
            ))}
          </div>
        </section>
      )}

      {/* Match Forecasts Section */}
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Target className="h-4 w-4 text-blue" />
            <h2 className="text-base font-semibold text-text">Upcoming Match Forecasts</h2>
          </div>
          {forecasts.length > 0 && (
            <Button
              size="sm"
              variant="outline"
              onPress={exportCsv}
              className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium cursor-pointer"
            >
              <Download className="h-3.5 w-3.5 text-blue" />
              <span>Export all forecasts</span>
            </Button>
          )}
        </div>
        <p className="text-xs leading-5 text-subtext0">Long-range percentages use today’s known form; they cannot account for matches, injuries or transfers that have not happened yet. Refresh after results for updated probabilities.</p>

        {forecasts.length === 0 ? (
          <EmptyState icon="🎯" message="No current match forecasts available." suggestion="Forecasts update when upcoming domestic fixtures are ingested." />
        ) : (
          <>
          <div className="flex flex-wrap items-center justify-between gap-3 text-xs text-subtext0">
            <label className="flex items-center gap-2">
              <span>League</span>
              <select
                value={forecastLeague}
                onChange={(event) => { setForecastLeague(event.target.value); setVisibleForecasts(30); }}
                className="min-h-9 rounded-lg border border-surface1 bg-mantle px-2 text-text"
              >
                <option value="all">All leagues</option>
                {forecastLeagues.map((league) => (
                  <option key={league} value={league}>{LEAGUE_NAMES[league] || league}</option>
                ))}
              </select>
            </label>
            <span>Showing {Math.min(visibleForecasts, filteredForecasts.length)} of {filteredForecasts.length} forecasts</span>
          </div>
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            {filteredForecasts.slice(0, visibleForecasts).map((f, idx) => {
              const homePct = Number((f.home_probability * 100).toFixed(0));
              const drawPct = Number((f.draw_probability * 100).toFixed(0));
              const awayPct = Number((f.away_probability * 100).toFixed(0));
              const confidence = Math.max(f.home_probability, f.draw_probability, f.away_probability);

              return (
                <div
                  key={`${f.match_date}_${f.home.team_id}_${f.away.team_id}_${idx}`}
                  className="p-4 rounded-xl bg-surface0 border border-surface1 hover:border-surface2 transition-colors space-y-3"
                >
                  <div className="flex items-center justify-between text-xs text-subtext0">
                    <span className="flex items-center gap-1.5 text-overlay1 font-mono">
                      <Calendar className="h-3.5 w-3.5" />
                      {f.match_date}
                    </span>
                    <span className="rounded bg-surface1 px-2 py-0.5 font-medium text-subtext1">
                      {f.competition}
                    </span>
                  </div>

                  {/* Match Teams */}
                  <div className="flex items-center justify-between text-sm font-semibold">
                    <span className="text-text truncate w-[45%] text-left">{f.home.name}</span>
                    <span className="text-overlay0 text-xs px-2">vs</span>
                    <span className="text-text truncate w-[45%] text-right">{f.away.name}</span>
                  </div>

                  {/* Outcome Probabilities Progress Bar */}
                  <div className="space-y-1.5 pt-1">
                    <div className="flex h-3 w-full rounded-full overflow-hidden bg-mantle">
                      <div
                        className="bg-blue transition-all"
                        style={{ width: `${homePct}%` }}
                        title={`Home win: ${homePct}%`}
                      />
                      <div
                        className="bg-overlay1 transition-all"
                        style={{ width: `${drawPct}%` }}
                        title={`Draw: ${drawPct}%`}
                      />
                      <div
                        className="bg-peach transition-all"
                        style={{ width: `${awayPct}%` }}
                        title={`Away win: ${awayPct}%`}
                      />
                    </div>

                    <div className="flex justify-between text-[11px] font-mono text-subtext0">
                      <span className="text-blue font-medium">Home: {homePct}%</span>
                      <span className="text-overlay1">Draw: {drawPct}%</span>
                      <span className="text-peach font-medium">Away: {awayPct}%</span>
                    </div>
                  </div>

                  {/* Predicted Outcome Badge */}
                  <div className="pt-1 flex items-center justify-between border-t border-surface1/60 text-xs">
                    <span className="text-subtext0">Forecast:</span>
                    <span className="flex items-center gap-1 font-semibold text-text">
                      <CheckCircle2 className="h-3.5 w-3.5 text-green" />
                      {f.predicted_result === 'Home'
                        ? `${f.home.name} Win`
                        : f.predicted_result === 'Away'
                        ? `${f.away.name} Win`
                        : 'Draw'}
                    </span>
                  </div>
                  <p className={`text-[11px] font-semibold ${confidence >= strongThreshold ? 'text-teal' : 'text-subtext0'}`}>
                    {confidence >= strongThreshold ? 'High-confidence tier' : confidence >= 0.6 ? 'Moderate lean' : 'Open match'} · {(confidence * 100).toFixed(1)}% strongest outcome
                  </p>
                </div>
              );
            })}
          </div>
          {visibleForecasts < filteredForecasts.length && (
            <Button variant="outline" onPress={() => setVisibleForecasts((count) => count + 30)}>
              Show 30 more forecasts
            </Button>
          )}
          </>
        )}
      </div>

      {/* Model Calibration Section */}
      {calibrationChartData.length > 0 && (
        <div className="rounded-xl border border-surface1 bg-surface0 p-5 space-y-4">
          <div className="flex items-center gap-2">
            <BarChart2 className="h-4 w-4 text-teal" />
            <h2 className="text-base font-semibold text-text">Reliability Calibration Diagram</h2>
          </div>
          <p className="text-xs text-subtext0">
            Compares model mean forecasted probabilities against actual observed outcomes in holdout validation matches.
          </p>

          <div className="h-64 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={calibrationChartData} margin={{ top: 10, right: 20, left: -10, bottom: 5 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#313244" vertical={false} />
                <XAxis dataKey="outcome" stroke="#7f849c" fontSize={11} />
                <YAxis stroke="#7f849c" fontSize={11} unit="%" />
                <Tooltip
                  contentStyle={{ backgroundColor: '#181825', borderColor: '#45475a', borderRadius: '8px', color: '#cdd6f4' }}
                  formatter={(val) => [`${val}%`]}
                />
                <Legend wrapperStyle={{ fontSize: '11px', color: '#bac2de' }} />
                <Bar dataKey="Predicted Probability" fill="#89b4fa" radius={[4, 4, 0, 0]} />
                <Bar dataKey="Observed Win Rate" fill="#a6e3a1" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}

      {leagueBacktest.length > 0 && (
        <Card className="rounded-xl border border-surface1 bg-surface0 p-5 space-y-3">
          <h2 className="text-base font-semibold text-text">Holdout by league</h2>
          <p className="text-xs text-subtext0">The same later test period, split by competition. Small samples are less reliable.</p>
          <div className="overflow-x-auto">
            <table className="w-full min-w-[420px] text-left text-xs">
              <thead className="border-b border-surface1 text-subtext0"><tr><th className="py-2">League</th><th className="py-2 text-right">Matches</th><th className="py-2 text-right">Accuracy</th><th className="py-2 text-right">Log loss</th></tr></thead>
              <tbody>{leagueBacktest.map((row) => <tr key={row.league} className="border-b border-surface1/50 last:border-0"><td className="py-2 font-semibold text-text">{LEAGUE_NAMES[row.league] || row.league}</td><td className="py-2 text-right text-subtext1">{row.matches}</td><td className="py-2 text-right text-subtext1">{(row.accuracy * 100).toFixed(1)}%</td><td className="py-2 text-right text-subtext1">{row.log_loss.toFixed(3)}</td></tr>)}</tbody>
            </table>
          </div>
        </Card>
      )}

      {(outcomeBacktest.length > 0 || walkForward.length > 0) && (
        <div className="grid gap-4 xl:grid-cols-2">
          {outcomeBacktest.length > 0 && (
            <Card className="rounded-xl border border-surface1 bg-surface0 p-5">
              <h2 className="text-base font-semibold text-text">Home, draw and away audit</h2>
              <p className="mt-1 text-xs text-subtext0">Recall shows how often each real outcome was found; precision shows how often that prediction was right.</p>
              <div className="mt-3 overflow-x-auto"><table className="w-full min-w-[380px] text-xs">
                <thead className="border-b border-surface1 text-subtext0"><tr><th className="py-2 text-left">Outcome</th><th className="text-right">Actual</th><th className="text-right">Predicted</th><th className="text-right">Recall</th><th className="text-right">Precision</th></tr></thead>
                <tbody>{outcomeBacktest.map((row) => <tr key={row.outcome} className="border-b border-surface1/50 last:border-0"><td className="py-2 font-semibold text-text">{row.outcome}</td><td className="text-right text-subtext1">{row.matches}</td><td className="text-right text-subtext1">{row.predicted}</td><td className="text-right text-subtext1">{row.recall === null ? '—' : `${(row.recall * 100).toFixed(1)}%`}</td><td className="text-right text-subtext1">{row.precision === null ? '—' : `${(row.precision * 100).toFixed(1)}%`}</td></tr>)}</tbody>
              </table></div>
            </Card>
          )}
          {walkForward.length > 0 && (
            <Card className="rounded-xl border border-surface1 bg-surface0 p-5">
              <h2 className="text-base font-semibold text-text">Season-by-season walk-forward</h2>
              <p className="mt-1 text-xs text-subtext0">Each season is scored using only earlier seasons for fitting and calibration.</p>
              <div className="mt-3 overflow-x-auto"><table className="w-full min-w-[360px] text-xs">
                <thead className="border-b border-surface1 text-subtext0"><tr><th className="py-2 text-left">Season</th><th className="text-right">Games</th><th className="text-right">Accuracy</th><th className="text-right">Baseline</th><th className="text-right">Log loss</th></tr></thead>
                <tbody>{walkForward.map((row) => <tr key={row.season} className="border-b border-surface1/50 last:border-0"><td className="py-2 font-semibold text-text">{row.season}/{String(row.season + 1).slice(-2)}</td><td className="text-right text-subtext1">{row.matches}</td><td className="text-right text-subtext1">{(row.accuracy * 100).toFixed(1)}%</td><td className="text-right text-subtext1">{(row.baseline_accuracy * 100).toFixed(1)}%</td><td className="text-right text-subtext1">{row.log_loss.toFixed(3)}</td></tr>)}</tbody>
              </table></div>
            </Card>
          )}
        </div>
      )}

      <Card className="rounded-xl border border-surface1 bg-surface0 p-5">
        <h2 className="text-base font-semibold text-text">Published forecast record</h2>
        <p className="mt-1 text-xs text-subtext0">Forecasts are kept as issued and matched with results after refresh. Re-forecasts for the same match are separate records.</p>
        <p className="mt-3 text-sm font-semibold text-text">
          {forecastRecord?.resolved ? `${forecastRecord.correct ?? 0} correct of ${forecastRecord.resolved} resolved (${((forecastRecord.accuracy ?? 0) * 100).toFixed(1)}%)` : 'No published forecasts resolved yet'}
          <span className="ml-2 text-xs font-normal text-subtext0">· {forecastRecord?.issued ?? 0} issued</span>
        </p>
        <p className="mt-1 text-xs text-subtext1">
          {forecastRecord?.rps != null
            ? `Live RPS ${forecastRecord.rps.toFixed(4)} on ${forecastRecord.matches_scored} matches (last forecast before kick-off)${forecastRecord.walk_forward_rps != null ? ` vs ${forecastRecord.walk_forward_rps.toFixed(4)} walk-forward; lower is better` : ''}.`
            : 'Live RPS appears once forecast matches have results.'}
        </p>
        {forecastHistory.length > 0 && <div className="mt-3 overflow-x-auto"><table className="w-full min-w-[500px] text-xs">
          <thead className="border-b border-surface1 text-subtext0"><tr><th className="py-2 text-left">Issued</th><th className="text-left">Fixture</th><th className="text-left">Pick</th><th className="text-left">Result</th></tr></thead>
          <tbody>{forecastHistory.map((row) => <tr key={`${row.model_id}-${row.competition}-${row.match_date}-${row.home.team_id}-${row.away.team_id}`} className="border-b border-surface1/50 last:border-0"><td className="py-2 text-subtext1">{row.issued_at.slice(0, 10)}</td><td className="text-subtext1">{row.home.name} – {row.away.name}</td><td className="text-subtext1">{row.predicted_result}</td><td className={row.actual_result ? row.actual_result === row.predicted_result ? 'text-green' : 'text-red' : 'text-subtext0'}>{row.actual_result || 'Pending'}</td></tr>)}</tbody>
        </table></div>}
      </Card>
    </div>
  );
}

export default function PredictionsPage() {
  return (
    <div className="space-y-6">
      <PageHeader icon={Target} eyebrow="Model intelligence" title="Predictions & Model Card" description="Review calibrated match probabilities, chronological holdout evidence, and every supported league's title outlook." />

      <Suspense fallback={<LoadingSkeleton lines={8} />}>
        <PredictionsContent />
      </Suspense>
    </div>
  );
}
