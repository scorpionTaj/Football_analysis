import type { SourceMeta } from '@/lib/api/types';

export function SourceBadge({ meta }: { meta: SourceMeta | null }) {
  if (!meta) return null;
  return (
    <div className="inline-flex items-center gap-1.5 rounded-full bg-surface0 px-2.5 py-1 text-xs text-subtext0">
      <span className="font-medium text-subtext1">{meta.source}</span>
      <span className="text-overlay0">·</span>
      <span>{meta.coverage}</span>
      {meta.freshness && (
        <>
          <span className="text-overlay0">·</span>
          <time className="text-overlay1" title={meta.freshness}>
            {meta.freshness.slice(0, 10)}
          </time>
        </>
      )}
    </div>
  );
}
