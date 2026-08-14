import { clsx } from 'clsx';
import { twMerge } from 'tailwind-merge';

interface SelectOption {
  value: string;
  label: string;
  disabled?: boolean;
}

interface SelectProps extends React.SelectHTMLAttributes<HTMLSelectElement> {
  label?: string;
  error?: string;
  options: SelectOption[];
  placeholder?: string;
}

export function Select({ label, error, options, placeholder, className, id, ...props }: SelectProps) {
  const selectId = id || label?.toLowerCase().replace(/\s+/g, '-');

  return (
    <div className="space-y-1.5">
      {label && (
        <label htmlFor={selectId} className="block text-sm font-semibold text-ink">
          {label}
        </label>
      )}
      <div className="relative">
        <select
          id={selectId}
          className={twMerge(
            clsx(
              // S5 accessibility: text-base (16px) prevents iOS Safari
              // auto-zoom when the select receives focus.
              'w-full px-3 py-2.5 rounded-lg text-base',
              'bg-cream border border-border',
              'text-ink',
              'focus:outline-none focus:ring-2 focus:ring-blue/20 focus:border-blue',
              'transition-all duration-150 appearance-none cursor-pointer',
              'hover:border-ink/30',
              error ? 'border-error focus:ring-error/20 focus:border-error' : '',
              className
            )
          )}
          {...props}
        >
          {placeholder && (
            <option value="" disabled>
              {placeholder}
            </option>
          )}
          {options.map((opt) => (
            <option key={opt.value} value={opt.value} disabled={opt.disabled}>
              {opt.label}
            </option>
          ))}
        </select>
        <div className="absolute inset-y-0 right-0 flex items-center px-3 pointer-events-none">
          <svg aria-hidden="true" className="w-4 h-4 text-ink/50" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
          </svg>
        </div>
      </div>
      {error && <p className="text-sm text-error">{error}</p>}
    </div>
  );
}
