import { useState, useEffect } from 'react';
import { createPortal } from 'react-dom';
import type { ModelEntry } from '../../api/admin/providers';
import { getModelId } from '../../api/admin/providers';

interface ModelSelectorProps {
  open: boolean;
  onClose: () => void;
  selectedModels: ModelEntry[];
  availableModels: ModelEntry[];
  onConfirm: (models: string[]) => void;
  title?: string;
}

/** 从模型名称推断能力标签（前端展示用） */
function inferCapabilities(modelId: string): string[] {
  const lower = modelId.toLowerCase();
  if (/rerank|re-rank|cross-encoder|bge-reranker/.test(lower)) return ['rerank'];
  if (/^text-|embed|bge-|bce-|e5-|gte-|voyage-|jina-emb|text-embedding/.test(lower)) return ['embedding'];
  return ['chat'];
}

/** 从 ModelEntry 提取能力列表 */
function getCapabilities(m: ModelEntry): string[] {
  if (typeof m === 'object' && m.capabilities && m.capabilities.length > 0) return m.capabilities;
  return inferCapabilities(getModelId(m));
}

const CAP_COLORS: Record<string, string> = {
  chat: 'rgba(59,130,246,0.2)',
  embedding: 'rgba(74,222,128,0.2)',
  rerank: 'rgba(168,85,247,0.2)',
  reasoning: 'rgba(251,191,36,0.2)',
  'image-generation': 'rgba(244,114,182,0.2)',
};

export function ModelSelector({
  open, onClose, selectedModels, availableModels, onConfirm, title = '选择模型'
}: ModelSelectorProps) {
  const [search, setSearch] = useState('');
  const [selected, setSelected] = useState<Set<string>>(new Set(
    selectedModels.map(getModelId)
  ));

  useEffect(() => {
    if (open) {
      setSelected(new Set(selectedModels.map(getModelId)));
      setSearch('');
    }
  }, [open, selectedModels]);

  // Group models by vendor prefix
  const groups = (() => {
    const map = new Map<string, ModelEntry[]>();
    const filtered = availableModels.filter(m => {
      const id = getModelId(m).toLowerCase();
      if (search && !id.includes(search.toLowerCase())) return false;
      return true;
    });
    for (const m of filtered) {
      const id = getModelId(m);
      const parts = id.split('/');
      const vendor = parts.length > 1 ? parts[0] : 'other';
      if (!map.has(vendor)) map.set(vendor, []);
      map.get(vendor)!.push(m);
    }
    return Array.from(map.entries()).map(([name, models]) => ({ name, models }));
  })();

  const toggleModel = (id: string) => {
    setSelected(prev => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id); else next.add(id);
      return next;
    });
  };

  const addAllFromGroup = (groupModels: ModelEntry[]) => {
    setSelected(prev => {
      const next = new Set(prev);
      for (const m of groupModels) next.add(getModelId(m));
      return next;
    });
  };

  const removeAllFromGroup = (groupModels: ModelEntry[]) => {
    setSelected(prev => {
      const next = new Set(prev);
      for (const m of groupModels) next.delete(getModelId(m));
      return next;
    });
  };

  if (!open) return null;

  return createPortal(
    <div style={{ position: 'fixed', inset: 0, zIndex: 9999 }}>
      <div style={{ position: 'absolute', inset: 0, background: 'rgba(0,0,0,0.5)' }} onClick={onClose} />
      <div style={{
        position: 'absolute', top: '50%', left: '50%', transform: 'translate(-50%,-50%)',
        width: 'min(600px, 90vw)', maxHeight: '80vh',
        background: 'var(--bg-card)', borderRadius: 12, border: '1px solid var(--border)',
        display: 'flex', flexDirection: 'column', overflow: 'hidden',
      }}>
        {/* Header */}
        <div style={{ padding: '14px 16px 10px', borderBottom: '1px solid var(--border-light)' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 10 }}>
            <span style={{ fontSize: 15, fontWeight: 600, color: 'var(--text-primary)' }}>{title}</span>
            <button onClick={onClose} style={{ background: 'none', border: 'none', color: 'var(--text-tertiary)', cursor: 'pointer', fontSize: 16 }}>✕</button>
          </div>
          <input value={search} onChange={e => setSearch(e.target.value)}
            placeholder="搜索模型 ID 或名称"
            style={{
              width: '100%', padding: '7px 12px', borderRadius: 6,
              background: 'rgba(0,0,0,0.2)', border: '1px solid var(--border)',
              color: 'var(--text-primary)', fontSize: 13, outline: 'none', fontFamily: 'inherit',
            }} />
        </div>

        {/* Model list */}
        <div style={{ flex: 1, overflowY: 'auto', padding: '8px 0' }}>
          {groups.length === 0 ? (
            <div style={{ textAlign: 'center', padding: 40, color: 'var(--text-tertiary)', fontSize: 13 }}>
              未找到匹配的模型
            </div>
          ) : groups.map(group => {
            const allSelected = group.models.every(m => selected.has(getModelId(m)));
            const someSelected = group.models.some(m => selected.has(getModelId(m)));
            return (
              <div key={group.name} style={{ marginBottom: 4 }}>
                <div style={{
                  display: 'flex', alignItems: 'center', padding: '6px 16px',
                  background: 'rgba(0,0,0,0.1)', cursor: 'pointer',
                }} onClick={() => allSelected ? removeAllFromGroup(group.models) : addAllFromGroup(group.models)}>
                  <span style={{ fontSize: 10, marginRight: 6, color: 'var(--text-tertiary)' }}>
                    {allSelected ? '▼' : '▶'}
                  </span>
                  <span style={{ fontSize: 13, fontWeight: 500, color: 'var(--text-primary)' }}>{group.name}</span>
                  <span style={{
                    marginLeft: 6, padding: '1px 6px', borderRadius: 8, fontSize: 10,
                    background: someSelected ? 'rgba(74,222,128,0.15)' : 'rgba(255,255,255,0.06)',
                    color: someSelected ? 'var(--accent-green)' : 'var(--text-tertiary)',
                  }}>{group.models.filter(m => selected.has(getModelId(m))).length}/{group.models.length}</span>
                  <span style={{ marginLeft: 'auto', fontSize: 16, color: 'var(--text-secondary)' }}>
                    {allSelected ? '−' : '+'}
                  </span>
                </div>
                {group.models.map(model => {
                  const id = getModelId(model);
                  const isActive = selected.has(id);
                  const caps = getCapabilities(model);
                  return (
                    <div key={id} onClick={() => toggleModel(id)} style={{
                      display: 'flex', alignItems: 'center', padding: '8px 16px 8px 36px',
                      cursor: 'pointer',
                      background: isActive ? 'rgba(59,130,246,0.06)' : 'transparent',
                      borderBottom: '1px solid rgba(255,255,255,0.03)',
                    }}>
                      <div style={{
                        width: 24, height: 24, borderRadius: '50%', marginRight: 10,
                        background: isActive ? 'var(--accent-blue)' : 'rgba(255,255,255,0.1)',
                        display: 'flex', alignItems: 'center', justifyContent: 'center',
                        fontSize: 11, color: '#fff',
                      }}>
                        {isActive ? '✓' : id[0].toUpperCase()}
                      </div>
                      <div style={{ flex: 1, minWidth: 0 }}>
                        <span style={{
                          fontSize: 13,
                          color: isActive ? 'var(--text-primary)' : 'var(--text-secondary)',
                        }}>{id}</span>
                        {caps.length > 0 && (
                          <div style={{ display: 'flex', gap: 4, marginTop: 2 }}>
                            {caps.map(cap => (
                              <span key={cap} style={{
                                fontSize: 9, padding: '1px 5px', borderRadius: 3,
                                background: CAP_COLORS[cap] || 'rgba(255,255,255,0.08)',
                                color: 'var(--text-secondary)',
                                textTransform: 'capitalize',
                              }}>{cap}</span>
                            ))}
                          </div>
                        )}
                      </div>
                      <span style={{ fontSize: 16, color: 'var(--text-tertiary)' }}>
                        {isActive ? '−' : '+'}
                      </span>
                    </div>
                  );
                })}
              </div>
            );
          })}
        </div>

        {/* Footer */}
        <div style={{
          padding: '12px 16px', borderTop: '1px solid var(--border-light)',
          display: 'flex', justifyContent: 'space-between', alignItems: 'center',
        }}>
          <span style={{ fontSize: 12, color: 'var(--text-tertiary)' }}>
            已选 {selected.size} 个模型
          </span>
          <div style={{ display: 'flex', gap: 8 }}>
            <button onClick={onClose} style={{
              padding: '7px 16px', borderRadius: 6, fontSize: 13,
              background: 'transparent', border: '1px solid var(--border)',
              color: 'var(--text-secondary)', cursor: 'pointer', fontFamily: 'inherit',
            }}>取消</button>
            <button onClick={() => onConfirm(Array.from(selected))} style={{
              padding: '7px 20px', borderRadius: 6, fontSize: 13, fontWeight: 500,
              background: 'var(--accent)', border: 'none',
              color: '#fff', cursor: 'pointer', fontFamily: 'inherit',
            }}>确认 ({selected.size})</button>
          </div>
        </div>
      </div>
    </div>,
    document.body
  );
}