import { cn } from '../../utils/cn';
import { TASK_STATUS_MAP } from '../../utils/constants';

interface StatusBadgeProps {
  status: string;
  className?: string;
}

export function StatusBadge({ status, className }: StatusBadgeProps) {
  const config = TASK_STATUS_MAP[status] ?? { label: status, color: 'text-slate-400' };
  return (
    <span className={cn('text-xs font-medium', config.color, className)}>
      {config.label}
    </span>
  );
}
