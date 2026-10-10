import type { SourceMeta } from '@/lib/api/types';

export function SourceBadge({ meta }: { meta: SourceMeta | null }) {
  if (!meta) return null;
  return (
    <div className="inline-flex min-w-0 max-w-full items-center gap-1.5 rounded-md border border-surface1 px-2 py-0.5 text-xs text-subtext0" title={`${meta.source} · ${meta.coverage}`}>
      <span className="size-1.5 shrink-0 rounded-full bg-positive" aria-hidden="true" />
      <span className="shrink-0 font-medium text-subtext1">{meta.source}</span>
      <span className="min-w-0 truncate">{meta.coverage}</span>
      {meta.freshness && (
        <time className="hidden shrink-0 text-overlay1 sm:inline" title={meta.freshness}>
          · {meta.freshness.slice(0, 10)}
        </time>
      )}
    </div>
  );
}
