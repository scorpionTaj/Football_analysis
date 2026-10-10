import type { ReactNode } from 'react';
import type { LucideIcon } from 'lucide-react';

/** Compact page title bar: eyebrow, the page's only h1, one-line description, actions on the right. */
export function PageHeader({
  title,
  description,
  icon: Icon,
  eyebrow,
  action,
}: {
  title: string;
  description?: string;
  icon?: LucideIcon;
  eyebrow?: string;
  action?: ReactNode;
}) {
  return (
    <header className="flex flex-col justify-between gap-4 border-b border-surface1 pb-5 sm:flex-row sm:items-end">
      <div className="min-w-0">
        {eyebrow ? (
          <p className="mb-1 flex items-center gap-1.5 text-xs font-medium text-subtext0">
            {Icon ? <Icon className="size-3.5 text-accent" aria-hidden="true" /> : null}
            {eyebrow}
          </p>
        ) : null}
        <h1 className="text-balance text-2xl font-semibold tracking-tight text-text sm:text-[28px] sm:leading-9">{title}</h1>
        {description ? <p className="mt-1.5 max-w-3xl text-sm text-subtext0">{description}</p> : null}
      </div>
      {action ? <div className="flex shrink-0 flex-wrap items-center gap-2">{action}</div> : null}
    </header>
  );
}
