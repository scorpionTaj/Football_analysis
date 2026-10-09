import type { ReactNode } from 'react';

/** The one h2 style: 14px semibold title with an optional muted description line. */
export function SectionHeading({
  children,
  description,
  level = 2,
}: {
  children: ReactNode;
  description?: ReactNode;
  level?: 2 | 3;
}) {
  const Heading = level === 2 ? 'h2' : 'h3';
  return (
    <div className="min-w-0">
      <Heading className="text-sm font-semibold text-text">{children}</Heading>
      {description ? <p className="mt-0.5 text-xs text-subtext0">{description}</p> : null}
    </div>
  );
}
