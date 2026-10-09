import type { ReactNode } from 'react';
import { SectionHeading } from './section-heading';

/** The one card surface: hairline border, 12px radius, 16px padding, optional header row. */
export function Panel({
  title,
  description,
  actions,
  children,
  className = '',
  bodyClassName = '',
  as: Tag = 'section',
  id,
}: {
  title?: ReactNode;
  description?: ReactNode;
  actions?: ReactNode;
  children?: ReactNode;
  className?: string;
  bodyClassName?: string;
  as?: 'section' | 'div' | 'article';
  id?: string;
}) {
  const header = title || actions;
  return (
    <Tag id={id} className={`rounded-xl border border-surface1 bg-surface0 ${className}`}>
      {header ? (
        <div className="flex flex-wrap items-start justify-between gap-3 border-b border-surface1 px-4 py-3">
          {title ? <SectionHeading description={description}>{title}</SectionHeading> : <span />}
          {actions ? <div className="flex shrink-0 flex-wrap items-center gap-2">{actions}</div> : null}
        </div>
      ) : null}
      <div className={`p-4 ${bodyClassName}`}>{children}</div>
    </Tag>
  );
}
