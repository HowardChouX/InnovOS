import { AlertCircle } from 'lucide-react';

interface InlineConfirmModalProps {
  open: boolean;
  title: string;
  message: string;
  confirmText?: string;
  cancelText?: string;
  confirmColor?: 'red' | 'blue' | 'yellow' | 'green';
  onConfirm: () => void;
  onCancel: () => void;
}

const colorClasses = {
  red: {
    title: 'text-red-400',
    btn: 'bg-red-500 hover:bg-red-600',
  },
  blue: {
    title: 'text-blue-400',
    btn: 'bg-blue-500 hover:bg-blue-600',
  },
  yellow: {
    title: 'text-yellow-400',
    btn: 'bg-yellow-500 hover:bg-yellow-600',
  },
  green: {
    title: 'text-green-400',
    btn: 'bg-green-500 hover:bg-green-600',
  },
} as const;

export function InlineConfirmModal({
  open,
  title,
  message,
  confirmText = '确认',
  cancelText = '取消',
  confirmColor = 'red',
  onConfirm,
  onCancel,
}: InlineConfirmModalProps) {
  if (!open) return null;

  const c = colorClasses[confirmColor];

  return (
    <div
      className="fixed inset-0 z-[300] flex items-center justify-center bg-black/60"
      onClick={onCancel}
    >
      <div
        className="bg-[var(--bg-card)] rounded-xl border border-[var(--border)] p-6 w-[360px] max-w-[90vw] shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className={`flex items-center gap-2 mb-3 text-[15px] font-semibold ${c.title}`}>
          <AlertCircle className="w-5 h-5" />
          {title}
        </div>
        <div className="text-[13px] text-slate-400 leading-relaxed mb-5">{message}</div>
        <div className="flex justify-end gap-2.5">
          <button
            onClick={onCancel}
            className="px-3.5 py-1.5 rounded-md text-xs bg-slate-500/10 border border-[var(--border-light)] text-slate-400 hover:bg-slate-500/15 transition-colors cursor-pointer font-[inherit]"
          >
            {cancelText}
          </button>
          <button
            onClick={onConfirm}
            className={`px-3.5 py-1.5 rounded-md text-xs border-none text-white transition-colors cursor-pointer font-[inherit] ${c.btn}`}
          >
            {confirmText}
          </button>
        </div>
      </div>
    </div>
  );
}
