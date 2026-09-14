'use client';

import { usePathname, useRouter, useSearchParams } from 'next/navigation';
import { useCallback } from 'react';

/**
 * Read and write shareable filter state from URL search params.
 * Keeps competition, season, team, venue, stage, and metric in the URL.
 */
export function useFilterParams() {
  const searchParams = useSearchParams();
  const pathname = usePathname();
  const router = useRouter();

  const get = useCallback(
    (key: string) => searchParams.get(key),
    [searchParams],
  );

  const getNumber = useCallback(
    (key: string) => {
      const v = searchParams.get(key);
      return v ? Number(v) : undefined;
    },
    [searchParams],
  );

  const set = useCallback(
    (updates: Record<string, string | number | null | undefined>) => {
      const params = new URLSearchParams(searchParams.toString());
      for (const [key, value] of Object.entries(updates)) {
        if (value === null || value === undefined || value === '') {
          params.delete(key);
        } else {
          params.set(key, String(value));
        }
      }
      const qs = params.toString();
      router.push(qs ? `${pathname}?${qs}` : pathname, { scroll: false });
    },
    [searchParams, pathname, router],
  );

  return {
    competition: get('competition'),
    season: getNumber('season'),
    team: get('team'),
    venue: get('venue'),
    stage: get('stage'),
    metric: get('metric'),
    cursor: get('cursor'),
    set,
    get,
    getNumber,
  };
}
