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
  let beforePrevious = Array.from({ length: b.length + 1 }, (_, index) => index);
  let previous = beforePrevious;
  for (let i = 1; i <= a.length; i += 1) {
    const current = Array.from({ length: b.length + 1 }, () => 0);
    current[0] = i;
    for (let j = 1; j <= b.length; j += 1) {
      current[j] = Math.min(
        previous[j] + 1,
        current[j - 1] + 1,
        previous[j - 1] + (a[i - 1] === b[j - 1] ? 0 : 1),
      );
      if (i > 1 && j > 1 && a[i - 1] === b[j - 2] && a[i - 2] === b[j - 1]) {
        current[j] = Math.min(current[j], beforePrevious[j - 2] + 1);
      }
    }
    beforePrevious = previous;
    previous = current;
  }
  return previous[b.length];
}

const MIN_FUZZY_SCORE = 75;

export function fuzzyScore(query: string, value: string): number {
  const needle = normalizeSearch(query);
  const candidate = normalizeSearch(value);
  if (!needle || !candidate) return 0;
  if (needle === candidate) return 100;
  const words = candidate.split(' ');
  if (words.some((word) => word === needle)) return 98;
  if (words.some((word) => word.startsWith(needle))) return 94;
  if (needle.length >= 3 && candidate.includes(needle)) return 88;
  if (needle.length < 4) return 0;
  const nearbyParts = [candidate, ...words].filter(
    (part) => Math.abs(part.length - needle.length) <= Math.max(2, Math.floor(needle.length / 3)),
  );
  const distances = nearbyParts.map((part) => {
    const distance = editDistance(needle, part);
    return 100 * (1 - distance / Math.max(needle.length, part.length, 1));
  });
  return distances.length ? Math.max(...distances) : 0;
}

export function fuzzyMatch(query: string, values: Array<string | null | undefined>): boolean {
  if (!normalizeSearch(query)) return true;
  return values.some((value) => fuzzyScore(query, value || '') >= MIN_FUZZY_SCORE);
}

export function fuzzySort<T>(query: string, rows: T[], text: (row: T) => string): T[] {
  return rows
    .map((row) => ({ row, score: fuzzyScore(query, text(row)) }))
    .filter(({ score }) => score >= MIN_FUZZY_SCORE)
    .sort((a, b) => b.score - a.score || text(a.row).localeCompare(text(b.row)))
    .map(({ row }) => row);
}
