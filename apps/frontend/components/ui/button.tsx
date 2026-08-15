import { clsx } from 'clsx';
import { twMerge } from 'tailwind-merge';

type ButtonVariant = 'primary' | 'secondary' | 'outline' | 'ghost' | 'danger';
type ButtonSize = 'sm' | 'md' | 'lg';

interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  size?: ButtonSize;
  loading?: boolean;
  children: React.ReactNode;
}

const variantClasses: Record<ButtonVariant, string> = {
  primary: 'bg-coral text-white hover:bg-coral-dark shadow-fab hover:shadow-lg',
  secondary: 'bg-cream text-ink border border-border hover:bg-soft hover:border-ink/30',
  outline: 'border border-border text-ink55 hover:bg-soft hover:text-ink',
  ghost: 'text-ink55 hover:bg-soft hover:text-ink',
  danger: 'bg-error text-white hover:bg-red-700',
};

const sizeClasses: Record<ButtonSize, string> = {
  sm: 'px-3 py-1.5 text-xs',
  md: 'px-4 py-2 text-sm',
  lg: 'px-5 py-2.5 text-sm',
};

export function Button({
  variant = 'primary',
  size = 'md',
  loading = false,
  className,
  disabled,
  children,
  ...props
}: ButtonProps) {
  return (
    <button
      className={twMerge(
        clsx(
          'inline-flex items-center justify-center gap-2 rounded-lg font-semibold',
          'transition-all duration-150',
          'disabled:opacity-50 disabled:cursor-not-allowed disabled:hover:translate-y-0',
          'hover:-translate-y-0.5 active:translate-y-0',
          variantClasses[variant],
          sizeClasses[size],
          className
        )
      )}
      disabled={disabled || loading}
      aria-busy={loading || undefined}
      {...props}
    >
      {loading && (
        <svg aria-hidden="true" className="animate-spin h-4 w-4" viewBox="0 0 24 24" fill="none">
          <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
          <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
        </svg>
      )}
      {children}
    </button>
  );
}
