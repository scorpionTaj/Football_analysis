/** Lightweight accent-insensitive fuzzy matching for all client-side search fields. */

export function normalizeSearch(value: string): string {
  return value
    .normalize('NFKD')
    .replace(/[\u0300-\u036f]/g, '')
    .toLocaleLowerCase()
    .replace(/[^a-z0-9]+/g, ' ')
    .trim();
}

function editDistance(a: string, b: string): number {
  const previous = Array.from({ length: b.length + 1 }, (_, index) => index);
  for (let i = 1; i <= a.length; i += 1) {
    let diagonal = previous[0];
    previous[0] = i;
    for (let j = 1; j <= b.length; j += 1) {
      const above = previous[j];
      previous[j] = Math.min(
        previous[j] + 1,
        previous[j - 1] + 1,
        diagonal + (a[i - 1] === b[j - 1] ? 0 : 1),
      );
      diagonal = above;
    }
  }
  return previous[b.length];
}

export function fuzzyScore(query: string, value: string): number {
  const needle = normalizeSearch(query);
  const candidate = normalizeSearch(value);
  if (!needle || !candidate) return 0;
  if (needle === candidate) return 100;
  const containedAt = candidate.indexOf(needle);
  if (containedAt >= 0) return 92 - Math.min(containedAt, 20);
  const words = candidate.split(' ');
  const distances = [candidate, ...words].map((part) => {
    const distance = editDistance(needle, part);
    return 100 * (1 - distance / Math.max(needle.length, part.length, 1));
  });
  return Math.max(...distances);
}

export function fuzzyMatch(query: string, values: Array<string | null | undefined>): boolean {
  if (!normalizeSearch(query)) return true;
  return values.some((value) => fuzzyScore(query, value || '') >= 58);
}

export function fuzzySort<T>(query: string, rows: T[], text: (row: T) => string): T[] {
  return rows
    .map((row) => ({ row, score: fuzzyScore(query, text(row)) }))
    .filter(({ score }) => score >= 58)
    .sort((a, b) => b.score - a.score || text(a.row).localeCompare(text(b.row)))
    .map(({ row }) => row);
}
