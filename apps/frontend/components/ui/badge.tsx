import { clsx } from 'clsx';
import { twMerge } from 'tailwind-merge';

type BadgeVariant = 'default' | 'coral' | 'green' | 'amber' | 'blue' | 'neutral';

interface BadgeProps extends React.HTMLAttributes<HTMLSpanElement> {
  variant?: BadgeVariant;
  size?: 'sm' | 'md';
}

const variantClasses: Record<BadgeVariant, string> = {
  default: 'bg-soft text-ink/70',
  coral: 'bg-coral-pale text-coral-dark',
  green: 'bg-green-pale text-green-800',
  amber: 'bg-amber-pale text-amber-800',
  blue: 'bg-blue-pale text-blue',
  neutral: 'bg-soft text-ink/60',
};

const sizeClasses = {
  sm: 'px-2.5 py-0.5 text-xs',
  md: 'px-3 py-1 text-sm',
};

export function Badge({ variant = 'default', size = 'sm', className, children, ...props }: BadgeProps) {
  return (
    <span
      className={twMerge(clsx('inline-flex items-center rounded-full font-semibold', variantClasses[variant], sizeClasses[size], className))}
      {...props}
    >
      {children}
    </span>
  );
}

// Status-specific badges
export type MatterStatus = 'new' | 'processing' | 'analysis_ready' | 'pending_human_review' | 'missing_information' | 'contact_client' | 'in_progress' | 'closed' | 'archived';

export const statusBadgeVariant: Record<MatterStatus, BadgeVariant> = {
  new: 'neutral',
  processing: 'amber',
  analysis_ready: 'green',
  pending_human_review: 'blue',
  missing_information: 'coral',
  contact_client: 'blue',
  in_progress: 'default',
  closed: 'neutral',
  archived: 'neutral',
};

export const statusLabels: Record<MatterStatus, string> = {
  new: 'Nuevo',
  processing: 'Procesando',
  analysis_ready: 'Análisis listo',
  pending_human_review: 'Pendiente revisión',
  missing_information: 'Info incompleta',
  contact_client: 'Contactar cliente',
  in_progress: 'En gestión',
  closed: 'Cerrado',
  archived: 'Archivado',
};

export type UrgencyLevel = 'low' | 'medium' | 'high' | 'urgent';

export const urgencyBadgeVariant: Record<UrgencyLevel, BadgeVariant> = {
  low: 'green',
  medium: 'amber',
  high: 'coral',
  urgent: 'coral',
};

export const urgencyLabels: Record<UrgencyLevel, string> = {
  low: 'Baja',
  medium: 'Media',
  high: 'Alta',
  urgent: 'Urgente',
};

interface MatterStatusBadgeProps {
  status: MatterStatus;
  size?: 'sm' | 'md';
}

export function MatterStatusBadge({ status, size = 'sm' }: MatterStatusBadgeProps) {
  return (
    <Badge variant={statusBadgeVariant[status]} size={size}>
      {statusLabels[status]}
    </Badge>
  );
}

interface UrgencyBadgeProps {
  level: UrgencyLevel;
  size?: 'sm' | 'md';
}

export function UrgencyBadge({ level, size = 'sm' }: UrgencyBadgeProps) {
  return (
    <Badge variant={urgencyBadgeVariant[level]} size={size}>
      {urgencyLabels[level]}
    </Badge>
  );
}
