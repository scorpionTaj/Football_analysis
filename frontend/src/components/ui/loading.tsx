const SKELETON_WIDTHS = ['90%', '75%', '85%', '95%', '70%', '80%', '65%', '88%'];

export function LoadingSkeleton({ lines = 3 }: { lines?: number }) {
  return (
    <div className="animate-pulse space-y-3" role="status" aria-label="Loading">
      {Array.from({ length: lines }).map((_, i) => (
        <div
          key={i}
          className="h-4 rounded bg-surface1"
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
    <div className="rounded-lg border border-red/20 bg-red/5 p-4" role="alert">
      <p className="font-semibold text-red">{title}</p>
      {detail && <p className="mt-1 text-sm text-subtext0">{detail}</p>}
      {retry && (
        <button
          onClick={retry}
          className="mt-3 rounded bg-surface1 px-3 py-1.5 text-sm font-medium text-text hover:bg-surface2 transition-colors"
        >
          Try again
        </button>
      )}
    </div>
  );
}

export function EmptyState({
  icon = '📋',
  message = 'No data available',
  suggestion,
}: {
  icon?: string;
  message?: string;
  suggestion?: string;
}) {
  return (
    <div className="flex flex-col items-center justify-center py-12 text-center">
      <span className="text-4xl" role="img" aria-hidden="true">
        {icon}
      </span>
      <p className="mt-3 text-lg font-medium text-subtext1">{message}</p>
      {suggestion && (
        <p className="mt-1 text-sm text-subtext0">{suggestion}</p>
      )}
    </div>
  );
}
