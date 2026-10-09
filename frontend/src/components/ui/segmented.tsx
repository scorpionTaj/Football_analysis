/** Compact segmented control (tabs, venue switches): pressed-state buttons in one bordered track. */
export function Segmented<T extends string>({
  value,
  onChange,
  options,
  label,
}: {
  value: T;
  onChange: (value: T) => void;
  options: readonly { value: T; label: string }[];
  label: string;
}) {
  return (
    <div role="group" aria-label={label} className="inline-flex max-w-full flex-wrap gap-0.5 rounded-lg border border-surface1 bg-mantle p-0.5">
      {options.map((option) => {
        const active = option.value === value;
        return (
          <button
            key={option.value}
            type="button"
            aria-pressed={active}
            onClick={() => onChange(option.value)}
            className={`h-7 rounded-md px-2.5 text-xs font-medium transition-colors ${
              active ? 'bg-surface0 text-text shadow-sm shadow-crust/20' : 'text-subtext0 hover:text-text'
            }`}
          >
            {option.label}
          </button>
        );
      })}
    </div>
  );
}
