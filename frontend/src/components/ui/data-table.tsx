import type { ReactNode, ThHTMLAttributes, TdHTMLAttributes } from 'react';
import { ArrowDown, ArrowUp, ArrowUpDown, Search } from 'lucide-react';

/**
 * Plain <table> markup (so row/column header roles stay intact) with the shared look:
 * sticky header, hairline rows, tabular numbers, horizontal scroll inside its own box.
 */
export function DataTable({
  children,
  minWidth = 560,
  caption,
  className = '',
}: {
  children: ReactNode;
  minWidth?: number;
  caption?: string;
  className?: string;
}) {
  return (
    <div className={`overflow-x-auto ${className}`}>
      <table className="w-full border-collapse text-left text-[13px] tabular-nums" style={{ minWidth }}>
        {caption ? <caption className="sr-only">{caption}</caption> : null}
        {children}
      </table>
    </div>
  );
}

export function THead({ children }: { children: ReactNode }) {
  return <thead className="sticky top-0 z-[1] bg-surface0 text-xs text-subtext0">{children}</thead>;
}

export function TBody({ children }: { children: ReactNode }) {
  return <tbody className="[&>tr]:border-t [&>tr]:border-surface1 [&>tr:hover]:bg-surface1/40">{children}</tbody>;
}

type Align = 'left' | 'right' | 'center';
const ALIGN: Record<Align, string> = { left: 'text-left', right: 'text-right', center: 'text-center' };

export function Th({ align = 'left', className = '', ...props }: ThHTMLAttributes<HTMLTableCellElement> & { align?: Align }) {
  return <th scope="col" className={`h-9 whitespace-nowrap px-3 font-medium ${ALIGN[align]} ${className}`} {...props} />;
}

export function Td({ align = 'left', className = '', ...props }: TdHTMLAttributes<HTMLTableCellElement> & { align?: Align }) {
  return <td className={`h-9 px-3 text-text ${ALIGN[align]} ${className}`} {...props} />;
}

/** Sortable column header: a button inside the <th>, with aria-sort reflecting the state. */
export function SortTh({
  children,
  dir,
  onSort,
  align = 'left',
  className = '',
}: {
  children: ReactNode;
  dir?: 'asc' | 'desc';
  onSort: () => void;
  align?: Align;
  className?: string;
}) {
  const Icon = dir === 'asc' ? ArrowUp : dir === 'desc' ? ArrowDown : ArrowUpDown;
  return (
    <th scope="col" aria-sort={dir === 'asc' ? 'ascending' : dir === 'desc' ? 'descending' : 'none'}
      className={`h-9 whitespace-nowrap px-1.5 font-medium ${ALIGN[align]} ${className}`}>
      <button type="button" onClick={onSort}
        className={`inline-flex items-center gap-1 rounded px-1.5 py-1 transition-colors hover:text-text ${dir ? 'text-text' : ''} ${align === 'right' ? 'flex-row-reverse' : ''}`}>
        {children}
        <Icon className={`size-3 shrink-0 ${dir ? 'text-accent' : 'text-overlay0'}`} aria-hidden="true" />
      </button>
    </th>
  );
}

/** Compact fuzzy filter box for a table toolbar, with a live "n of m" count. */
export function TableFilter({
  value,
  onChange,
  label,
  placeholder = 'Filter…',
  shown,
  total,
  className = '',
}: {
  value: string;
  onChange: (value: string) => void;
  label: string;
  placeholder?: string;
  shown?: number;
  total?: number;
  className?: string;
}) {
  return (
    <span className={`flex items-center gap-2 ${className}`}>
      <span className="relative">
        <Search className="pointer-events-none absolute left-2.5 top-1/2 size-3.5 -translate-y-1/2 text-overlay0" aria-hidden="true" />
        <input type="search" aria-label={label} placeholder={placeholder} value={value} onChange={(event) => onChange(event.target.value)}
          className="h-8 w-44 rounded-lg border border-surface1 bg-surface0 pl-8 pr-2.5 text-[13px] text-text placeholder:text-overlay0 focus:border-accent [&::-webkit-search-cancel-button]:hidden" />
      </span>
      {value && shown != null && total != null ? <span className="text-xs tabular-nums text-subtext0">{shown} of {total}</span> : null}
    </span>
  );
}
