'use client';

import { CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { Panel } from '@/components/ui/panel';
import { axisProps, gridProps, legendProps, SEMANTIC, SERIES, tooltipProps } from '@/lib/chart-theme';

export interface TrajectoryPoint { season: string; Points: number; GoalsScored: number; GoalsConceded: number }
export interface FormPoint { date: string; PPG: number }
export interface Percentile { label: string; percentile: number }

export function ClubCharts({
  club,
  trajectory,
  rollingForm,
  formWindow,
  percentiles,
}: {
  club: string;
  trajectory: TrajectoryPoint[];
  rollingForm: FormPoint[];
  formWindow: number;
  percentiles: Percentile[];
}) {
  return (
    <>
      {trajectory.length > 0 && (
        <Panel title={`${club} — performance trajectory`} description="Points and goals per season">
          <div className="h-72 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={trajectory} margin={{ top: 4, right: 12, left: -16, bottom: 0 }}>
                <CartesianGrid {...gridProps} />
                <XAxis dataKey="season" {...axisProps} />
                <YAxis {...axisProps} />
                <Tooltip {...tooltipProps} />
                <Legend {...legendProps} />
                <Line type="monotone" dataKey="Points" stroke={SERIES[0]} strokeWidth={2} dot={{ r: 3, fill: SERIES[0] }} />
                <Line type="monotone" dataKey="GoalsScored" name="Goals scored" stroke={SEMANTIC.positive} strokeWidth={1.5} dot={false} />
                <Line type="monotone" dataKey="GoalsConceded" name="Goals conceded" stroke={SEMANTIC.negative} strokeWidth={1.5} dot={false} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </Panel>
      )}

      <div className="grid gap-4 lg:grid-cols-[1.4fr_1fr]">
        <Panel title={`Rolling ${formWindow}-match form`} description="Points per game over the last matches">
          <div className="h-60">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={rollingForm} margin={{ top: 4, right: 8, left: -20, bottom: 0 }}>
                <CartesianGrid {...gridProps} />
                <XAxis dataKey="date" {...axisProps} minTickGap={32} />
                <YAxis domain={[0, 3]} {...axisProps} />
                <Tooltip {...tooltipProps} />
                <Line type="monotone" dataKey="PPG" stroke={SERIES[0]} strokeWidth={2} dot={false} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </Panel>
        <Panel title="Percentile profile" description="Against every club in the same competitions and seasons">
          <div className="space-y-4">
            {percentiles.map((row) => (
              <div key={row.label}>
                <div className="mb-1 flex justify-between text-xs">
                  <span className="text-subtext0">{row.label}</span>
                  <span className="font-semibold tabular-nums text-text">{row.percentile}th</span>
                </div>
                <div className="h-1.5 overflow-hidden rounded-full bg-surface1">
                  <div className="h-full rounded-full bg-accent" style={{ width: `${row.percentile}%` }} />
                </div>
              </div>
            ))}
          </div>
        </Panel>
      </div>
    </>
  );
}
