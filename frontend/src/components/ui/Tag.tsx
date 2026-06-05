import { cn } from '../../utils/cn';

interface TagProps {
  label: string;
  color?: 'blue' | 'slate';
  removable?: boolean;
  onRemove?: () => void;
}

export function Tag({ label, color = 'slate', removable, onRemove }: TagProps) {
  return (
    <span
      className={cn(
        'inline-flex items-center gap-1 px-3 py-1 rounded-full text-xs border',
        color === 'blue'
          ? 'bg-blue-900/30 text-blue-300 border-blue-800'
          : 'bg-slate-800 text-slate-400 border-slate-700'
      )}
    >
      {label}
      {removable && (
        <button onClick={onRemove} className="ml-1 hover:text-white">
          <i className="fa-solid fa-xmark text-[10px]" />
        </button>
      )}
    </span>
  );
}
