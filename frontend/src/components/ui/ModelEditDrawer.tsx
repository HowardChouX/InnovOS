import { useState, useEffect } from 'react';
import { createPortal } from 'react-dom';
import { providersApi, type ModelEntry } from '../../api/admin/providers';

const CAP_COLORS: Record<string, string> = {
  chat: 'rgba(59,130,246,0.2)',
  embedding: 'rgba(74,222,128,0.2)',
  rerank: 'rgba(250,204,21,0.2)',
  reasoning: 'rgba(168,85,247,0.2)',
  'function-call': 'rgba(236,72,153,0.2)',
  'image-recognition': 'rgba(251,146,60,0.2)',
};

const CAP_LABELS: Record<string, string> = {
  chat: '对话',
  embedding: '嵌入',
  rerank: '重排',
  reasoning: '推理',
  'function-call': '工具',
  'image-recognition': '视觉',
};

const CAP_ORDER = ['chat', 'embedding', 'rerank', 'reasoning', 'function-call', 'image-recognition'];

interface Props {
  open: boolean;
  onClose: () => void;
  providerId: string;
  model: ModelEntry | null;
  onSave: (modelId: string, data: Partial<ModelEntry>) => void;
}

export function ModelEditDrawer({ open, onClose, providerId, model, onSave }: Props) {
  const [enabled, setEnabled] = useState(true);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (model) {
      setEnabled(model.isEnabled ?? true);
    }
  }, [model]);

  if (!open || !model) return null;

  const caps: string[] = (model.capabilities || []);
  const sortedCaps = CAP_ORDER.filter(c => caps.includes(c));

  const handleSave = async () => {
    setSaving(true);
    try {
      await providersApi.updateModel(providerId, model.id, { is_enabled: enabled });
      onSave(model.id, { ...model, isEnabled: enabled });
    } catch { /* */ }
    finally { setSaving(false); onClose(); }
  };

  return createPortal(
    <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.4)', display: 'flex', justifyContent: 'flex-end', zIndex: 9999 }}>
      <div style={{ width: 420, maxWidth: '90vw', background: 'var(--bg-card)', height: '100%', overflowY: 'auto', borderLeft: '1px solid var(--border)', padding: 24 }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 20 }}>
          <div style={{ fontSize: 15, fontWeight: 600, color: 'var(--text-primary)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', flex: 1 }}>{model.label || model.id}</div>
          <button onClick={onClose} style={{ width: 28, height: 28, borderRadius: 6, background: 'rgba(0,0,0,0.2)', border: '1px solid var(--border)', color: 'var(--text-secondary)', cursor: 'pointer', fontSize: 14, display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>✕</button>
        </div>

        {/* 能力标签 */}
        <div style={{ marginBottom: 20 }}>
          <div style={{ fontSize: 11, color: 'var(--text-tertiary)', marginBottom: 8, textTransform: 'uppercase', letterSpacing: '0.5px' }}>能力</div>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
            {sortedCaps.map(c => (
              <span key={c} style={{
                padding: '3px 10px', borderRadius: 4, fontSize: 11, fontWeight: 500,
                background: CAP_COLORS[c] || 'rgba(255,255,255,0.08)',
                color: 'var(--text-primary)',
              }}>{CAP_LABELS[c] || c}</span>
            ))}
            {sortedCaps.length === 0 && <span style={{ fontSize: 11, color: 'var(--text-tertiary)' }}>无能力信息</span>}
          </div>
        </div>

        {/* 配置项 */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '10px 14px', borderRadius: 8, background: 'rgba(0,0,0,0.2)', border: '1px solid var(--border)' }}>
            <span style={{ fontSize: 13, color: 'var(--text-primary)' }}>启用</span>
            <button onClick={() => setEnabled(!enabled)} style={{
              width: 40, height: 22, borderRadius: 11, border: 'none', cursor: 'pointer', position: 'relative',
              background: enabled ? 'rgba(74,222,128,0.3)' : 'rgba(255,255,255,0.1)', transition: 'background 0.2s',
            }}>
              <div style={{
                width: 18, height: 18, borderRadius: '50%', position: 'absolute', top: 2,
                background: enabled ? 'var(--accent-green)' : 'var(--text-tertiary)',
                left: enabled ? 20 : 2, transition: 'left 0.2s',
              }} />
            </button>
          </div>

          {model.contextWindow ? (
            <div>
              <div style={{ fontSize: 11, color: 'var(--text-tertiary)', marginBottom: 4 }}>上下文窗口</div>
              <div style={{ padding: '8px 12px', borderRadius: 6, background: 'rgba(0,0,0,0.2)', border: '1px solid var(--border)', fontSize: 12, color: 'var(--text-muted)', fontFamily: 'monospace' }}>{model.contextWindow.toLocaleString()} tokens</div>
            </div>
          ) : null}

          {model.maxOutputTokens ? (
            <div>
              <div style={{ fontSize: 11, color: 'var(--text-tertiary)', marginBottom: 4 }}>最大输出</div>
              <div style={{ padding: '8px 12px', borderRadius: 6, background: 'rgba(0,0,0,0.2)', border: '1px solid var(--border)', fontSize: 12, color: 'var(--text-muted)', fontFamily: 'monospace' }}>{model.maxOutputTokens.toLocaleString()} tokens</div>
            </div>
          ) : null}

          {model.endpointTypes?.length ? (
            <div>
              <div style={{ fontSize: 11, color: 'var(--text-tertiary)', marginBottom: 4 }}>端点类型</div>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4 }}>
                {model.endpointTypes.map((et: string) => (
                  <span key={et} style={{ padding: '2px 8px', borderRadius: 4, fontSize: 10, background: 'rgba(59,130,246,0.1)', color: 'var(--accent-blue)', fontFamily: 'monospace', border: '1px solid rgba(59,130,246,0.2)' }}>{et}</span>
                ))}
              </div>
            </div>
          ) : null}

          {model.pricing ? (
            <div>
              <div style={{ fontSize: 11, color: 'var(--text-tertiary)', marginBottom: 4 }}>定价</div>
              <div style={{ padding: '8px 12px', borderRadius: 6, background: 'rgba(0,0,0,0.2)', border: '1px solid var(--border)', fontSize: 11, color: 'var(--text-muted)', fontFamily: 'monospace', whiteSpace: 'pre-wrap' }}>{JSON.stringify(model.pricing, null, 2)}</div>
            </div>
          ) : null}
        </div>

        <div style={{ marginTop: 24, display: 'flex', gap: 10, justifyContent: 'flex-end' }}>
          <button onClick={onClose} style={{ padding: '7px 16px', borderRadius: 6, fontSize: 13, background: 'transparent', border: '1px solid var(--border)', color: 'var(--text-secondary)', cursor: 'pointer', fontFamily: 'inherit' }}>取消</button>
          <button onClick={handleSave} disabled={saving} style={{ padding: '7px 16px', borderRadius: 6, fontSize: 13, background: 'var(--accent)', border: 'none', color: '#fff', cursor: 'pointer', fontFamily: 'inherit', opacity: saving ? 0.5 : 1 }}>{saving ? '保存中...' : '保存'}</button>
        </div>
      </div>
    </div>,
    document.body
  );
}
