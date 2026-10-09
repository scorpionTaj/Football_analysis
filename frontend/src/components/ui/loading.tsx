import { AlertTriangle, Inbox, type LucideIcon } from 'lucide-react';

const SKELETON_WIDTHS = ['90%', '75%', '85%', '95%', '70%', '80%', '65%', '88%'];

export function LoadingSkeleton({ lines = 3 }: { lines?: number }) {
  return (
    <div className="animate-pulse space-y-2.5" role="status" aria-label="Loading">
      {Array.from({ length: lines }).map((_, i) => (
        <div
          key={i}
          className="h-3.5 rounded bg-surface1"
          style={{ width: SKELETON_WIDTHS[i % SKELETON_WIDTHS.length] }}
        />
      ))}
      <span className="sr-only">Loading…</span>
    </div>
  );
}

export function ErrorMessage({
  title = 'Something went wrong',
  detail,
  retry,
}: {
  title?: string;
  detail?: string;
  retry?: () => void;
}) {
  return (
    <div className="flex gap-3 rounded-xl border border-negative/30 bg-negative/5 p-4" role="alert">
      <AlertTriangle className="mt-0.5 size-4 shrink-0 text-negative" aria-hidden="true" />
      <div className="min-w-0">
        <p className="text-sm font-semibold text-negative">{title}</p>
        {detail && <p className="mt-1 text-[13px] text-subtext0">{detail}</p>}
        {retry && (
          <button
            type="button"
            onClick={retry}
            className="mt-3 h-8 rounded-lg border border-surface1 bg-surface0 px-3 text-[13px] font-medium text-text transition-colors hover:bg-surface1"
          >
            Try again
          </button>
        )}
      </div>
    </div>
  );
}

/** `icon` accepts a Lucide icon; legacy emoji strings fall back to the default icon. */
export function EmptyState({
  icon,
  message = 'No data available',
  suggestion,
}: {
  icon?: LucideIcon | string;
  message?: string;
  suggestion?: string;
}) {
  const Icon = typeof icon === 'function' || (typeof icon === 'object' && icon) ? icon as LucideIcon : Inbox;
  return (
    <div className="flex flex-col items-center justify-center px-4 py-10 text-center">
      <span className="grid size-10 place-items-center rounded-lg border border-surface1 bg-mantle text-overlay0">
        <Icon className="size-5" aria-hidden="true" />
      </span>
      <p className="mt-3 text-sm font-medium text-text">{message}</p>
      {suggestion && <p className="mt-1 max-w-md text-[13px] text-subtext0">{suggestion}</p>}
    </div>
  );
}
