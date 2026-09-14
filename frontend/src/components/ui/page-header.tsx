import type { ReactNode } from 'react';
import type { LucideIcon } from 'lucide-react';
import { Card } from '@heroui/react';

export function PageHeader({
  title,
  description,
  icon: Icon,
  eyebrow = 'Football intelligence',
  action,
}: {
  title: string;
  description: string;
  icon: LucideIcon;
  eyebrow?: string;
  action?: ReactNode;
}) {
  return (
    <Card className="page-intro relative overflow-hidden border border-surface1/70 bg-surface0/75 px-5 py-5 shadow-xl shadow-crust/10 sm:px-6 sm:py-6">
      <div className="pointer-events-none absolute -right-16 -top-20 size-56 rounded-full bg-blue/10 blur-3xl" aria-hidden="true" />
      <div className="relative flex flex-col justify-between gap-5 sm:flex-row sm:items-center">
        <div className="flex min-w-0 items-start gap-4">
          <span className="grid size-12 shrink-0 place-items-center rounded-2xl border border-blue/20 bg-gradient-to-br from-blue/20 to-sapphire/5 text-blue shadow-inner">
            <Icon className="size-6" aria-hidden="true" />
          </span>
          <div className="min-w-0">
            <p className="mb-1 text-[11px] font-bold uppercase tracking-[0.18em] text-sapphire">{eyebrow}</p>
            <h1 className="text-balance text-2xl font-black tracking-[-0.035em] text-text sm:text-3xl">{title}</h1>
            <p className="mt-2 max-w-3xl text-sm leading-6 text-subtext0 sm:text-[15px]">{description}</p>
          </div>
        </div>
        {action ? <div className="shrink-0">{action}</div> : null}
      </div>
    </Card>
  );
}
