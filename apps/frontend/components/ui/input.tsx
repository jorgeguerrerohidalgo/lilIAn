import { clsx } from 'clsx';
import { twMerge } from 'tailwind-merge';

interface InputProps extends React.InputHTMLAttributes<HTMLInputElement> {
  label?: string;
  error?: string;
  hint?: string;
}

export function Input({ label, error, hint, className, id, ...props }: InputProps) {
  const inputId = id || label?.toLowerCase().replace(/\s+/g, '-');

  return (
    <div className="space-y-1.5">
      {label && (
        <label htmlFor={inputId} className="block text-sm font-semibold text-ink">
          {label}
        </label>
      )}
      <input
        id={inputId}
        className={twMerge(
          clsx(
            // S5 accessibility: text-base (16px) prevents iOS Safari auto-zoom
            // when the input receives focus.
            'w-full px-3 py-2.5 rounded-lg text-base',
            'bg-cream border border-border',
            'text-ink placeholder-ink/30',
            'focus:outline-none focus:ring-2 focus:ring-blue/20 focus:border-blue',
            'transition-all duration-150',
            error ? 'border-error focus:ring-error/20 focus:border-error' : '',
            className
          )
        )}
        {...props}
      />
      {error && <p className="text-sm text-error">{error}</p>}
      {hint && !error && <p className="text-sm text-ink/50">{hint}</p>}
    </div>
  );
}

interface TextareaProps extends React.TextareaHTMLAttributes<HTMLTextAreaElement> {
  label?: string;
  error?: string;
  hint?: string;
}

export function Textarea({ label, error, hint, className, id, ...props }: TextareaProps) {
  const textareaId = id || label?.toLowerCase().replace(/\s+/g, '-');

  return (
    <div className="space-y-1.5">
      {label && (
        <label htmlFor={textareaId} className="block text-sm font-semibold text-ink">
          {label}
        </label>
      )}
      <textarea
        id={textareaId}
        className={twMerge(
          clsx(
            // S5 accessibility: text-base (16px) prevents iOS Safari auto-zoom
            // when the textarea receives focus.
            'w-full px-3 py-2.5 rounded-lg text-base',
            'bg-cream border border-border',
            'text-ink placeholder-ink/30',
            'focus:outline-none focus:ring-2 focus:ring-blue/20 focus:border-blue',
            'transition-all duration-150 resize-none',
            error ? 'border-error focus:ring-error/20 focus:border-error' : '',
            className
          )
        )}
        {...props}
      />
      {error && <p className="text-sm text-error">{error}</p>}
      {hint && !error && <p className="text-sm text-ink/50">{hint}</p>}
    </div>
  );
}
