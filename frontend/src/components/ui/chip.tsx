import type { ReactNode } from 'react';
import type { Tone } from './stat';

const TONE: Record<Tone, string> = {
  neutral: 'bg-surface1 text-subtext1',
  accent: 'bg-accent/15 text-accent',
  positive: 'bg-positive/15 text-positive',
  negative: 'bg-negative/15 text-negative',
  warning: 'bg-warning/15 text-warning',
};

/** Status pill. Every tone keeps 4.5:1 text on its own tint (see the palette note in globals.css). */
export function Chip({ children, tone = 'neutral', className = '' }: { children: ReactNode; tone?: Tone; className?: string }) {
  return (
    <span className={`inline-flex items-center gap-1 rounded-md px-1.5 py-0.5 text-xs font-medium ${TONE[tone]} ${className}`}>
      {children}
    </span>
  );
}

/** One W/D/L form letter in the semantic colours. */
export function FormChip({ result }: { result: string }) {
  const tone: Tone = result === 'W' ? 'positive' : result === 'L' ? 'negative' : 'neutral';
  return <Chip tone={tone} className="size-5 justify-center px-0 font-semibold">{result}</Chip>;
}
