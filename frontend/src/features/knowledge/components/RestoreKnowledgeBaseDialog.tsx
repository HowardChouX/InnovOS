import { useState, useEffect } from 'react';
import { createPortal } from 'react-dom';
import { knowledgeApi } from '../../../api/knowledge';
import type { KnowledgeBase } from '../../../types/knowledge';

interface RestoreKnowledgeBaseDialogProps {
  open: boolean;
  base: KnowledgeBase | null;
  isRestoring?: boolean;
  onRestore: (input: { sourceBaseId: string; name: string; embeddingModelId: string; dimensions?: number }) => Promise<KnowledgeBase>;
  onOpenChange: (open: boolean) => void;
  onRestored: (base: KnowledgeBase) => void;
}

interface ModelOption {
  id: string;
  providerId: string;
  providerName: string;
  modelId: string;
  label: string;
}

const DEFAULT_DIMENSIONS = 1024;

const RestoreKnowledgeBaseDialog = ({
  open,
  base,
  isRestoring = false,
  onRestore,
  onOpenChange,
  onRestored,
}: RestoreKnowledgeBaseDialogProps) => {
  const [name, setName] = useState('');
  const [embeddingModelId, setEmbeddingModelId] = useState('');
  const [dimensions, setDimensions] = useState(String(DEFAULT_DIMENSIONS));
  const [embeddingModels, setEmbeddingModels] = useState<ModelOption[]>([]);
  const [loadingModels, setLoadingModels] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    if (open && base) {
      const defaultName = `${base.name} (恢复)`;
      setName(defaultName);
      setEmbeddingModelId('');
      setDimensions(String(DEFAULT_DIMENSIONS));
      setError('');
      loadModels();
    }
  }, [open, base?.id]);

  const loadModels = async () => {
    setLoadingModels(true);
    try {
      const res = await knowledgeApi.listEmbeddingModels();
      setEmbeddingModels(res.data || []);
    } catch {
      setEmbeddingModels([]);
    } finally {
      setLoadingModels(false);
    }
  };

  if (!open || !base) return null;

  const handleSubmit = async () => {
    const trimmedName = name.trim();
    if (!trimmedName) {
      setError('请输入名称');
      return;
    }
    if (!embeddingModelId) {
      setError('请选择嵌入模型');
      return;
    }
    setError('');
    try {
      const restored = await onRestore({
        sourceBaseId: base.id,
        name: trimmedName,
        embeddingModelId,
        dimensions: dimensions ? Number(dimensions) : DEFAULT_DIMENSIONS,
      });
      onRestored(restored);
      onOpenChange(false);
    } catch (e: any) {
      setError(e?.message || '恢复失败');
    }
  };

  return createPortal(
    <div
      className="fixed inset-0 z-[9999] flex items-center justify-center bg-black/50"
      onClick={() => onOpenChange(false)}
    >
      <div
        className="flex w-[480px] flex-col overflow-hidden rounded-xl border border-border bg-card"
        onClick={e => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between border-b border-border-light px-5 py-3.5">
          <span className="text-base font-semibold text-foreground">恢复知识库</span>
          <button
            onClick={() => onOpenChange(false)}
            className="text-foreground-muted hover:text-foreground"
          >
            <i className="fa-solid fa-xmark text-lg" />
          </button>
        </div>

        {/* Body */}
        <div className="flex-1 overflow-y-auto p-5">
          {/* Failure info */}
          <div className="mb-5 rounded-lg badge-danger p-3">
            <div className="flex items-center gap-2 text-sm font-medium text-accent-danger">
              <i className="fa-solid fa-circle-exclamation" />
              知识库处理失败
            </div>
            {base.error && (
              <div className="mt-1 text-xs text-accent-danger" style={{ opacity: 0.8 }}>
                错误信息：{base.error}
              </div>
            )}
            <div className="mt-2 text-xs text-foreground-muted">
              请选择新的嵌入模型和维度配置后重新创建。
            </div>
          </div>

          {/* Name */}
          <div className="mb-4">
            <label className="mb-1.5 block text-xs font-medium text-foreground">名称</label>
            <input
              value={name}
              onChange={e => setName(e.target.value)}
              placeholder="知识库名称"
              className="w-full rounded-md border border-border bg-background-muted px-3 py-2 text-sm text-foreground outline-none focus:ring-1 focus:ring-ring"
            />
          </div>

          {/* Embedding model */}
          <div className="mb-4">
            <label className="mb-1.5 block text-xs font-medium text-foreground">嵌入模型</label>
            <select
              value={embeddingModelId}
              onChange={e => setEmbeddingModelId(e.target.value)}
              className="w-full rounded-md border border-border bg-background-muted px-3 py-2 text-sm text-foreground outline-none focus:ring-1 focus:ring-ring"
            >
              <option value="">{loadingModels ? '加载中...' : '请选择嵌入模型'}</option>
              {embeddingModels.map(m => (
                <option key={m.id} value={m.id}>{m.label}</option>
              ))}
            </select>
          </div>

          {/* Dimensions */}
          <div className="mb-4">
            <label className="mb-1.5 block text-xs font-medium text-foreground">嵌入维度</label>
            <input
              value={dimensions}
              onChange={e => setDimensions(e.target.value)}
              placeholder="留空表示不设置"
              className="w-full rounded-md border border-border bg-background-muted px-3 py-2 text-sm text-foreground outline-none focus:ring-1 focus:ring-ring"
            />
          </div>

          {error && (
            <div className="rounded-md badge-danger px-3 py-2 text-xs">
              {error}
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="flex justify-end gap-2 border-t border-border-light px-5 py-3">
          <button
            onClick={() => onOpenChange(false)}
            className="rounded-md border border-border px-4 py-1.5 text-xs text-foreground-secondary hover:bg-accent"
          >
            取消
          </button>
          <button
            onClick={handleSubmit}
            disabled={isRestoring || !name.trim() || !embeddingModelId}
            className="rounded-md bg-primary px-4 py-1.5 text-xs text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
          >
            {isRestoring ? '恢复中...' : '确认恢复'}
          </button>
        </div>
      </div>
    </div>,
    document.body
  );
};

export default RestoreKnowledgeBaseDialog;
