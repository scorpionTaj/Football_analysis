import { ChevronDown } from 'lucide-react';

export interface SelectOption {
  value: string;
  label: string;
  group?: string;
  badge?: string;
}

/** Labelled native select (keeps the combobox role and keyboard behaviour), optional optgroups. */
export function Select({
  label,
  value,
  onChange,
  options,
  placeholder,
  hideLabel = false,
  className = '',
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  options: SelectOption[];
  placeholder?: string;
  hideLabel?: boolean;
  className?: string;
}) {
  const unique = Array.from(new Map(options.map((option) => [option.value, option])).values());
  const groups = Array.from(unique.reduce((map, option) => {
    const group = option.group || '';
    map.set(group, [...(map.get(group) || []), option]);
    return map;
  }, new Map<string, SelectOption[]>()).entries());
  const render = (option: SelectOption) => (
    <option key={option.value} value={option.value}>{option.badge ? `${option.badge} ${option.label}` : option.label}</option>
  );

  return (
    <label className={`flex min-w-0 flex-col gap-1 ${className}`}>
      <span className={hideLabel ? 'sr-only' : 'text-xs font-medium text-subtext0'}>{label}</span>
      <span className="relative">
        <select
          value={value}
          onChange={(event) => onChange(event.target.value)}
          aria-label={label}
          className="h-9 w-full cursor-pointer appearance-none rounded-lg border border-surface1 bg-surface0 pl-3 pr-8 text-[13px] text-text transition-colors hover:border-surface2 focus:border-accent"
        >
          {placeholder !== undefined ? <option value="">{placeholder}</option> : null}
          {groups.map(([group, entries]) => group
            ? <optgroup key={group} label={group}>{entries.map(render)}</optgroup>
            : entries.map(render))}
        </select>
        <ChevronDown className="pointer-events-none absolute right-2.5 top-1/2 size-4 -translate-y-1/2 text-overlay0" aria-hidden="true" />
      </span>
    </label>
  );
}
