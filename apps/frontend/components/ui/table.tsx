import { clsx } from 'clsx';
import { twMerge } from 'tailwind-merge';

interface TableProps extends React.TableHTMLAttributes<HTMLTableElement> {
  wrapperClassName?: string;
}

export function Table({ wrapperClassName, className, ...props }: TableProps) {
  return (
    <div className={twMerge(clsx('rounded-lg border border-border overflow-auto', wrapperClassName))}>
      <table className={twMerge(clsx('w-full text-sm text-left', className))} {...props} />
    </div>
  );
}

export function TableHeader({ className, children, ...props }: React.HTMLAttributes<HTMLTableSectionElement>) {
  return (
    <thead className={twMerge(clsx('bg-soft text-ink/60 border-b-2 border-border', className))} {...props}>
      {children}
    </thead>
  );
}

export function TableBody({ className, children, ...props }: React.HTMLAttributes<HTMLTableSectionElement>) {
  return (
    <tbody className={twMerge(clsx('divide-y divide-border', className))} {...props}>
      {children}
    </tbody>
  );
}

interface TableRowProps extends React.HTMLAttributes<HTMLTableRowElement> {
  hover?: boolean;
}

export function TableRow({ hover = true, className, children, ...props }: TableRowProps) {
  return (
    <tr className={twMerge(clsx(hover && 'hover:bg-soft transition-colors duration-100', className))} {...props}>
      {children}
    </tr>
  );
}

export function TableHead({ className, children, ...props }: React.ThHTMLAttributes<HTMLTableCellElement>) {
  return (
    <th className={twMerge(clsx('px-4 py-3 text-xs font-bold uppercase tracking-wider text-left', className))} {...props}>
      {children}
    </th>
  );
}

export function TableCell({ className, children, ...props }: React.TdHTMLAttributes<HTMLTableCellElement>) {
  return (
    <td className={twMerge(clsx('px-4 py-3 text-ink', className))} {...props}>
      {children}
    </td>
  );
}

interface TableEmptyProps {
  columns: number;
  message?: string;
}

export function TableEmpty({ columns, message = 'No hay datos disponibles' }: TableEmptyProps) {
  return (
    <tr>
      <td colSpan={columns} className="px-4 py-12 text-center text-ink/50">
        <div className="flex flex-col items-center gap-2">
          <svg aria-hidden="true" className="w-12 h-12 text-ink/20" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth={1}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
          </svg>
          <p className="text-sm">{message}</p>
        </div>
      </td>
    </tr>
  );
}

interface TableLoadingProps {
  columns: number;
  rows?: number;
}

export function TableLoading({ columns, rows = 5 }: TableLoadingProps) {
  return (
    <>
      {Array.from({ length: rows }).map((_, i) => (
        <tr key={i} className="animate-pulse">
          {Array.from({ length: columns }).map((_, j) => (
            <td key={j} className="px-4 py-3">
              <div className="h-4 bg-soft rounded w-3/4" />
            </td>
          ))}
        </tr>
      ))}
    </>
  );
}
