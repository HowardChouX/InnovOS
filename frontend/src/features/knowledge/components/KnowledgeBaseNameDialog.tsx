import { useState, useEffect } from 'react';
import { createPortal } from 'react-dom';

interface KnowledgeBaseNameDialogProps {
  open: boolean;
  initialName: string;
  isSubmitting?: boolean;
  onSubmit: (name: string) => Promise<void>;
  onOpenChange: (open: boolean) => void;
}

const KnowledgeBaseNameDialog = ({
  open,
  initialName,
  isSubmitting = false,
  onSubmit,
  onOpenChange,
}: KnowledgeBaseNameDialogProps) => {
  const [name, setName] = useState(initialName);
  const [error, setError] = useState('');

  useEffect(() => {
    if (open) {
      setName(initialName);
      setError('');
    }
  }, [initialName, open]);

  if (!open) return null;

  const handleSubmit = async () => {
    const trimmed = name.trim();
    if (!trimmed) {
      setError('请输入名称');
      return;
    }
    try {
      await onSubmit(trimmed);
      onOpenChange(false);
    } catch (e: any) {
      setError(e?.message || '重命名失败');
    }
  };

  return createPortal(
    <div
      className="fixed inset-0 z-[9999] flex items-center justify-center bg-black/50"
      onClick={() => onOpenChange(false)}
    >
      <div
        className="flex w-[400px] flex-col overflow-hidden rounded-xl border border-border bg-card"
        onClick={e => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between border-b border-border-light px-4 py-3.5">
          <span className="text-base font-semibold text-foreground">重命名知识库</span>
          <button
            onClick={() => onOpenChange(false)}
            className="text-foreground-muted hover:text-foreground"
          >
            <i className="fa-solid fa-xmark text-lg" />
          </button>
        </div>

        {/* Body */}
        <div className="p-4">
          <input
            autoFocus
            value={name}
            onChange={e => { setName(e.target.value); setError(''); }}
            onKeyDown={e => { if (e.key === 'Enter' && !isSubmitting) handleSubmit(); }}
            placeholder="名称"
            className="w-full rounded-md border border-border bg-background-muted px-3 py-2 text-sm text-foreground outline-none placeholder:text-foreground-muted/50 focus:ring-1 focus:ring-ring"
          />
          {error && (
            <div className="mt-2 text-xs text-accent-danger">{error}</div>
          )}
        </div>

        {/* Footer */}
        <div className="flex justify-end gap-2 border-t border-border-light px-4 py-3">
          <button
            onClick={() => onOpenChange(false)}
            className="rounded-md border border-border px-4 py-1.5 text-xs text-foreground-secondary hover:bg-accent"
          >
            取消
          </button>
          <button
            onClick={handleSubmit}
            disabled={isSubmitting || !name.trim()}
            className="rounded-md bg-primary px-4 py-1.5 text-xs text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
          >
            {isSubmitting ? '保存中...' : '确认'}
          </button>
        </div>
      </div>
    </div>,
    document.body
  );
};

export default KnowledgeBaseNameDialog;
