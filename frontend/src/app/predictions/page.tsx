'use client';

import { Card, Button, Chip } from '@heroui/react';
import { Suspense, useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import { api } from '@/lib/api/client';
import { queryKeys } from '@/lib/api/query-keys';
import { SourceBadge } from '@/components/ui/source-badge';
import { LoadingSkeleton, ErrorMessage, EmptyState } from '@/components/ui/loading';
import type { Forecast, CalibrationBin } from '@/lib/api/types';
import { Cpu, Target, CheckCircle2, TrendingUp, Download, Calendar, BarChart2 } from 'lucide-react';
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

function PredictionsContent() {
  const { data, isLoading, error, refetch } = useQuery({
    queryKey: queryKeys.predictions,
    queryFn: () => api.predictions(),
  });

  const forecasts = data?.forecasts || [];
  const calibration = data?.calibration || [];
  const metrics = data?.metrics || {};

  const accuracy = typeof metrics.accuracy === 'number' ? (metrics.accuracy * 100).toFixed(1) : null;
  const baseline = typeof metrics.baseline_accuracy === 'number' ? (metrics.baseline_accuracy * 100).toFixed(1) : null;
  const logLoss = typeof metrics.log_loss === 'number' ? metrics.log_loss.toFixed(3) : null;

  // Calibration chart data
  const calibrationChartData = useMemo(() => {
    return calibration.map((bin) => ({
      outcome: bin.predicted_outcome === 'Home' ? 'Home Win' : bin.predicted_outcome === 'Away' ? 'Away Win' : 'Draw',
      'Predicted Probability': Number((bin.mean_probability * 100).toFixed(1)),
      'Observed Win Rate': Number((bin.observed_rate * 100).toFixed(1)),
      samples: bin.samples,
    }));
  }, [calibration]);

  // CSV export handler
  const exportCsv = () => {
    const headers = ['Date', 'Competition', 'Home Team', 'Away Team', 'Predicted Result', 'Home %', 'Draw %', 'Away %'];
    const rows = forecasts.map((f) => [
      f.match_date,
      f.competition,
      `"${f.home.name}"`,
      `"${f.away.name}"`,
      f.predicted_result,
      (f.home_probability * 100).toFixed(1),
      (f.draw_probability * 100).toFixed(1),
      (f.away_probability * 100).toFixed(1),
    ]);
    const csvContent = [headers.join(','), ...rows.map((r) => r.join(','))].join('\n');
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
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 pt-1">
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
        </div>
      </Card>

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
              <span>Export Predictions</span>
            </Button>
          )}
        </div>

        {forecasts.length === 0 ? (
          <EmptyState icon="🎯" message="No current match forecasts available." suggestion="Forecasts update when upcoming domestic fixtures are ingested." />
        ) : (
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            {forecasts.map((f, idx) => {
              const homePct = Number((f.home_probability * 100).toFixed(0));
              const drawPct = Number((f.draw_probability * 100).toFixed(0));
              const awayPct = Number((f.away_probability * 100).toFixed(0));

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
                </div>
              );
            })}
          </div>
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
                  formatter={(val: any) => [`${val}%`]}
                />
                <Legend wrapperStyle={{ fontSize: '11px', color: '#bac2de' }} />
                <Bar dataKey="Predicted Probability" fill="#89b4fa" radius={[4, 4, 0, 0]} />
                <Bar dataKey="Observed Win Rate" fill="#a6e3a1" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}
    </div>
  );
}

export default function PredictionsPage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-text tracking-tight">Predictions & Model Cards</h1>
        <p className="text-sm text-subtext0 mt-1">
          Regularized softmax 3-way match probability forecasts, out-of-sample holdout metrics, and calibration curves.
        </p>
      </div>

      <Suspense fallback={<LoadingSkeleton lines={8} />}>
        <PredictionsContent />
      </Suspense>
    </div>
  );
}
