import { clsx } from 'clsx';
import { twMerge } from 'tailwind-merge';

interface CardProps extends React.HTMLAttributes<HTMLDivElement> {
  hover?: boolean;
  padding?: 'none' | 'sm' | 'md' | 'lg';
  elevated?: boolean;
}

const paddingClasses = {
  none: '',
  sm: 'p-4',
  md: 'p-5',
  lg: 'p-6',
};

export function Card({
  hover = false,
  padding = 'md',
  elevated = false,
  className,
  children,
  ...props
}: CardProps) {
  return (
    <div
      className={twMerge(
        clsx(
          'bg-cream rounded-lg border',
          elevated ? 'shadow-lg' : 'shadow',
          'border-border',
          hover && 'transition-all duration-150 hover:-translate-y-0.5 hover:shadow-lg cursor-pointer',
          paddingClasses[padding],
          className
        )
      )}
      {...props}
    >
      {children}
    </div>
  );
}

interface CardHeaderProps extends React.HTMLAttributes<HTMLDivElement> {
  title?: string;
  action?: React.ReactNode;
}

export function CardHeader({ title, action, className, children, ...props }: CardHeaderProps) {
  return (
    <div className={twMerge(clsx('flex items-center justify-between mb-4', className))} {...props}>
      {title ? (
        <h3 className="text-lg font-heading font-bold text-ink">{title}</h3>
      ) : (
        children
      )}
      {action}
    </div>
  );
}

interface CardTitleProps extends React.HTMLAttributes<HTMLHeadingElement> {
  children: React.ReactNode;
}

export function CardTitle({ className, children, ...props }: CardTitleProps) {
  return (
    <h3 className={twMerge(clsx('text-lg font-heading font-bold text-ink', className))} {...props}>
      {children}
    </h3>
  );
}

interface CardContentProps extends React.HTMLAttributes<HTMLDivElement> {
  children: React.ReactNode;
}

export function CardContent({ className, children, ...props }: CardContentProps) {
  return (
    <div className={twMerge(clsx('', className))} {...props}>
      {children}
    </div>
  );
}

interface StatCardProps extends React.HTMLAttributes<HTMLDivElement> {
  label: string;
  value: string | number;
  icon?: React.ReactNode;
  trend?: { value: number; isPositive: boolean };
}

export function StatCard({ label, value, icon, trend, className, ...props }: StatCardProps) {
  return (
    <div
      className={twMerge(
        clsx(
          'rounded-lg p-5 relative overflow-hidden',
          'bg-gradient-to-br from-ink to-blue text-white',
          className
        )
      )}
      {...props}
    >
      <div
        className="absolute top-0 right-0 w-28 h-28 rounded-full opacity-10"
        style={{ background: 'rgba(255,255,255,0.1)', transform: 'translate(30%, -30%)' }}
      />
      <div className="relative z-10">
        <p className="text-sm text-white/70">{label}</p>
        <div className="flex items-end gap-3 mt-1">
          <p className="text-3xl font-heading font-bold">{value}</p>
          {trend && (
            <span className={clsx('text-sm font-semibold mb-1', trend.isPositive ? 'text-green-300' : 'text-red-300')}>
              {trend.isPositive ? '+' : ''}{trend.value}%
            </span>
          )}
        </div>
        {icon && <div className="mt-3 opacity-80">{icon}</div>}
      </div>
    </div>
  );
}
