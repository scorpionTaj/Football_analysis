import type { SourceMeta } from '@/lib/api/types';

export function SourceBadge({ meta }: { meta: SourceMeta | null }) {
  if (!meta) return null;
  return (
    <div className="inline-flex min-w-0 max-w-full items-center gap-1.5 rounded-full bg-surface0 px-2.5 py-1 text-xs text-subtext0" title={`${meta.source} · ${meta.coverage}`}>
      <span className="shrink-0 font-medium text-subtext1">{meta.source}</span>
      <span className="shrink-0 text-overlay0">·</span>
      <span className="min-w-0 truncate">{meta.coverage}</span>
      {meta.freshness && (
        <span className="hidden shrink-0 items-center gap-1.5 sm:inline-flex">
          <span className="text-overlay0">·</span>
          <time className="text-overlay1" title={meta.freshness}>
            {meta.freshness.slice(0, 10)}
          </time>
        </span>
      )}
    </div>
  );
}
