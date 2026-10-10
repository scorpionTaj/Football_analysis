import type { ReactNode, ThHTMLAttributes, TdHTMLAttributes } from 'react';

/**
 * Plain <table> markup (so row/column header roles stay intact) with the shared look:
 * sticky header, hairline rows, tabular numbers, horizontal scroll inside its own box.
 */
export function DataTable({
  children,
  minWidth = 560,
  caption,
  className = '',
}: {
  children: ReactNode;
  minWidth?: number;
  caption?: string;
  className?: string;
}) {
  return (
    <div className={`overflow-x-auto ${className}`}>
      <table className="w-full border-collapse text-left text-[13px] tabular-nums" style={{ minWidth }}>
        {caption ? <caption className="sr-only">{caption}</caption> : null}
        {children}
      </table>
    </div>
  );
}

export function THead({ children }: { children: ReactNode }) {
  return <thead className="sticky top-0 z-[1] bg-surface0 text-xs text-subtext0">{children}</thead>;
}

export function TBody({ children }: { children: ReactNode }) {
  return <tbody className="[&>tr]:border-t [&>tr]:border-surface1 [&>tr:hover]:bg-surface1/40">{children}</tbody>;
}

type Align = 'left' | 'right' | 'center';
const ALIGN: Record<Align, string> = { left: 'text-left', right: 'text-right', center: 'text-center' };

export function Th({ align = 'left', className = '', ...props }: ThHTMLAttributes<HTMLTableCellElement> & { align?: Align }) {
  return <th scope="col" className={`h-9 whitespace-nowrap px-3 font-medium ${ALIGN[align]} ${className}`} {...props} />;
}

export function Td({ align = 'left', className = '', ...props }: TdHTMLAttributes<HTMLTableCellElement> & { align?: Align }) {
  return <td className={`h-9 px-3 text-text ${ALIGN[align]} ${className}`} {...props} />;
}
