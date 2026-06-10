import { useState, useEffect } from 'react';
import { createPortal } from 'react-dom';
import { useKnowledgeStore } from '../../store/useKnowledgeStore';

interface Props {
  open: boolean;
  onClose: () => void;
}

export default function CreateKnowledgeBaseDialog({ open, onClose }: Props) {
  const { createBase, groups, createBaseGroupId } = useKnowledgeStore();

  const [name, setName] = useState('');
  const [groupId, setGroupId] = useState<string | undefined>(createBaseGroupId);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    if (open) {
      setName('');
      setGroupId(createBaseGroupId);
      setError('');
    }
  }, [open, createBaseGroupId]);

  if (!open) return null;

  const handleSubmit = async () => {
    if (!name.trim()) { setError('请输入知识库名称'); return; }
    setError('');
    setSubmitting(true);
    try {
      await createBase(name.trim(), groupId, {});
      onClose();
    } catch (e: any) {
      setError(e?.message || '创建失败');
    } finally {
      setSubmitting(false);
    }
  };

  return createPortal(
    <div
      className="fixed inset-0 z-[9999] flex items-center justify-center bg-black/50"
      onClick={onClose}
    >
      <div
        className="flex w-[520px] max-h-[85vh] flex-col overflow-hidden rounded-xl border border-border bg-card"
        onClick={e => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between border-b border-border-light px-5 py-3.5">
          <span className="text-base font-semibold text-foreground">添加知识库</span>
          <button onClick={onClose} className="text-foreground-muted hover:text-foreground">
            <i className="fa-solid fa-xmark text-lg" />
          </button>
        </div>

        {/* Body */}
        <div className="flex-1 overflow-y-auto p-5 space-y-4">
          {/* 名称 */}
          <div>
            <label className="mb-1.5 block text-xs font-medium text-foreground">名称</label>
            <input
              autoFocus
              value={name}
              onChange={e => setName(e.target.value)}
              onKeyDown={e => { if (e.key === 'Enter' && !submitting) handleSubmit(); }}
              placeholder="知识库名称"
              className="w-full rounded-md border border-border bg-background-muted px-3 py-2 text-sm text-foreground outline-none placeholder:text-foreground-muted/50 focus:ring-1 focus:ring-ring"
            />
          </div>

          {/* 分组 */}
          {groups.length > 0 && (
            <div>
              <label className="mb-1.5 block text-xs font-medium text-foreground">分组</label>
              <select
                value={groupId ?? ''}
                onChange={e => setGroupId(e.target.value || undefined)}
                className="w-full rounded-md border border-border bg-background-muted px-3 py-2 text-sm text-foreground outline-none focus:ring-1 focus:ring-ring"
              >
                <option value="">未分组</option>
                {groups.map(g => (
                  <option key={g.id} value={g.id}>{g.name}</option>
                ))}
              </select>
            </div>
          )}

          {error && (
            <div className="rounded-md badge-danger px-3 py-2 text-xs">
              {error}
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="flex items-center justify-end border-t border-border-light px-5 py-3">
          <div className="flex gap-2">
            <button
              onClick={onClose}
              className="rounded-md border border-border px-4 py-1.5 text-xs text-foreground-secondary hover:bg-accent"
            >
              取消
            </button>
            <button
              onClick={handleSubmit}
              disabled={submitting || !name.trim()}
              className="rounded-md bg-primary px-5 py-1.5 text-xs font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
            >
              {submitting ? '创建中...' : '确认'}
            </button>
          </div>
        </div>
      </div>
    </div>,
    document.body
  );
}
