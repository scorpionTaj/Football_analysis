import { useMemo, useState } from 'react';
import { fuzzyMatch } from '@/lib/fuzzy';

export type SortDir = 'asc' | 'desc';
type Value = string | number | null | undefined;

/**
 * Client-side sort + fuzzy text filter for a table. Sort before paginating so the order
 * covers every row, not only the visible page. Clicking the active column flips direction;
 * a new column starts descending for numbers and ascending for text.
 */
export function useTableView<T, K extends string>(
  rows: readonly T[],
  {
    columns,
    initial,
    search,
  }: {
    columns: Record<K, (row: T) => Value>;
    initial?: { key: NoInfer<K>; dir: SortDir };
    search?: (row: T) => (string | null | undefined)[];
  },
) {
  const [sort, setSortState] = useState<{ key: K; dir: SortDir } | null>(initial ?? null);
  const [query, setQuery] = useState('');

  const view = useMemo(() => {
    const filtered = query.trim() && search ? rows.filter((row) => fuzzyMatch(query, search(row))) : [...rows];
    if (!sort) return filtered;
    const pick = columns[sort.key];
    const sign = sort.dir === 'asc' ? 1 : -1;
    return filtered.sort((a, b) => {
      const x = pick(a);
      const y = pick(b);
      if (x == null || x === '') return y == null || y === '' ? 0 : 1; // empty values always last
      if (y == null || y === '') return -1;
      return sign * (typeof x === 'number' && typeof y === 'number' ? x - y : String(x).localeCompare(String(y), undefined, { numeric: true }));
    });
  }, [rows, query, search, sort, columns]);

  const toggle = (key: K) => setSortState((current) => {
    if (current?.key === key) return { key, dir: current.dir === 'asc' ? 'desc' : 'asc' };
    const sample = rows.map(columns[key]).find((value) => value != null && value !== '');
    return { key, dir: typeof sample === 'number' ? 'desc' : 'asc' };
  });

  /** Props for <SortTh>: current direction (if this column is active) and the toggle. */
  const sortProps = (key: K) => ({ dir: sort?.key === key ? sort.dir : undefined, onSort: () => toggle(key) });

  return { rows: view, query, setQuery, sortProps, total: rows.length };
}
