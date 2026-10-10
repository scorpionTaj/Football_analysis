/**
 * One look for every recharts chart. Colours are CSS variables, so charts follow the light/dark
 * mode without re-rendering; pass these props instead of hard-coded hex values.
 */
import type { CSSProperties } from 'react';

export const SERIES = ['var(--series-1)', 'var(--series-2)', 'var(--series-3)', 'var(--series-4)'] as const;

export const OUTCOME = {
  home: 'var(--outcome-home)',
  draw: 'var(--outcome-draw)',
  away: 'var(--outcome-away)',
} as const;

export const SEMANTIC = {
  accent: 'var(--blue)',
  positive: 'var(--green)',
  negative: 'var(--red)',
  warning: 'var(--yellow)',
  muted: 'var(--chart-axis)',
} as const;

const tick = { fill: 'var(--chart-axis)', fontSize: 11 };

/** Spread onto <XAxis> / <YAxis>. */
export const axisProps = {
  stroke: 'var(--chart-grid)',
  tick,
  tickLine: false,
  axisLine: { stroke: 'var(--chart-grid)' },
} as const;

/** Spread onto <CartesianGrid>. */
export const gridProps = {
  stroke: 'var(--chart-grid)',
  strokeDasharray: '0',
  vertical: false,
} as const;

const tooltipContent: CSSProperties = {
  background: 'var(--mantle)',
  border: '1px solid var(--surface1)',
  borderRadius: 8,
  boxShadow: '0 8px 24px color-mix(in srgb, var(--crust) 35%, transparent)',
  color: 'var(--text)',
  fontSize: 12,
  padding: '6px 10px',
};

/** Spread onto <Tooltip>. */
export const tooltipProps = {
  contentStyle: tooltipContent,
  labelStyle: { color: 'var(--subtext0)', marginBottom: 2 },
  itemStyle: { color: 'var(--text)', padding: 0 },
  cursor: { fill: 'color-mix(in srgb, var(--surface1) 45%, transparent)', stroke: 'var(--surface2)' },
} as const;

/** Spread onto <Legend>. */
export const legendProps = {
  wrapperStyle: { fontSize: 12, color: 'var(--subtext0)' },
  iconSize: 8,
} as const;
