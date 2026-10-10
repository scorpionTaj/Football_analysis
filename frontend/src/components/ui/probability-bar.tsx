/** Home / draw / away probabilities as one stacked bar in the outcome colours, with labels. */
export function ProbabilityBar({
  home,
  draw,
  away,
  showLabels = true,
}: {
  home: number;
  draw: number;
  away: number;
  showLabels?: boolean;
}) {
  const pct = (value: number) => `${Math.round(value * 100)}%`;
  const parts = [
    { key: 'Home', value: home, color: 'var(--outcome-home)' },
    { key: 'Draw', value: draw, color: 'var(--outcome-draw)' },
    { key: 'Away', value: away, color: 'var(--outcome-away)' },
  ];
  return (
    <div>
      {showLabels ? (
        <div className="mb-1 flex justify-between text-xs tabular-nums text-subtext0">
          {parts.map((part) => (
            <span key={part.key} className="inline-flex items-center gap-1">
              <span className="size-2 rounded-sm" style={{ background: part.color }} aria-hidden="true" />
              {part.key} <span className="font-medium text-text">{pct(part.value)}</span>
            </span>
          ))}
        </div>
      ) : null}
      <div className="flex h-1.5 w-full gap-px overflow-hidden rounded-full bg-surface1" role="img"
        aria-label={`Home ${pct(home)}, draw ${pct(draw)}, away ${pct(away)}`}>
        {parts.map((part) => <div key={part.key} style={{ width: `${part.value * 100}%`, background: part.color }} />)}
      </div>
    </div>
  );
}
