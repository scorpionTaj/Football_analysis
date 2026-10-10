import type { ReactNode } from 'react';

export type Tone = 'neutral' | 'accent' | 'positive' | 'negative' | 'warning';

const VALUE_TONE: Record<Tone, string> = {
  neutral: 'text-text',
  accent: 'text-accent',
  positive: 'text-positive',
  negative: 'text-negative',
  warning: 'text-warning',
};

/** KPI tile: small label, large tabular value, optional hint or delta underneath. */
export function Stat({
  label,
  value,
  hint,
  tone = 'neutral',
  inset = false,
  className = '',
}: {
  label: ReactNode;
  value: ReactNode;
  hint?: ReactNode;
  tone?: Tone;
  /** Inside a Panel: sit on the darker mantle surface instead of a second card. */
  inset?: boolean;
  className?: string;
}) {
  return (
    <div className={`rounded-xl border border-surface1 px-4 py-3 ${inset ? 'bg-mantle' : 'bg-surface0'} ${className}`}>
      <p className="text-xs font-medium text-subtext0">{label}</p>
      <p className={`mt-1 text-2xl font-semibold tracking-tight tabular-nums ${VALUE_TONE[tone]}`}>{value}</p>
      {hint ? <p className="mt-0.5 text-xs text-subtext0">{hint}</p> : null}
    </div>
  );
}

/** Responsive grid for a row of Stat tiles. */
export function StatGrid({ children, className = '' }: { children: ReactNode; className?: string }) {
  return <div className={`grid grid-cols-2 gap-3 md:grid-cols-4 ${className}`}>{children}</div>;
}
