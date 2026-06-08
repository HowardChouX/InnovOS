import { useState, useEffect } from 'react';
import { createPortal } from 'react-dom';
import { useKnowledgeStore } from '../../store/useKnowledgeStore';
import { knowledgeApi } from '../../api/knowledge';

interface Props {
  open: boolean;
  onClose: () => void;
}

export function RagConfigPanel({ open, onClose }: Props) {
  const { bases, selectedBaseId } = useKnowledgeStore();
  const base = bases.find(b => b.id === selectedBaseId);

  const [chunkSize, setChunkSize] = useState(1024);
  const [chunkOverlap, setChunkOverlap] = useState(200);
  const [searchMode, setSearchMode] = useState('hybrid');
  const [hybridAlpha, setHybridAlpha] = useState(0.5);
  const [threshold, setThreshold] = useState(0.0);
  const [documentCount, setDocumentCount] = useState(10);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (base) {
      setChunkSize(base.chunkSize || 1024);
      setChunkOverlap(base.chunkOverlap || 200);
      setSearchMode(base.searchMode || 'hybrid');
      setHybridAlpha(base.hybridAlpha ?? 0.5);
      setThreshold(base.threshold ?? 0.0);
      setDocumentCount(base.documentCount ?? 10);
    }
  }, [base]);

  if (!open || !base) return null;

  const handleSave = async () => {
    if (!selectedBaseId) return;
    setSaving(true);
    try {
      await knowledgeApi.updateBase(selectedBaseId, {
        chunkSize, chunkOverlap, searchMode, hybridAlpha, threshold, documentCount,
      });
      onClose();
    } catch { /* */ } finally { setSaving(false); }
  };

  const inputStyle: React.CSSProperties = {
    width: '100%', padding: '7px 10px', borderRadius: 6, fontSize: 12,
    background: 'rgba(0,0,0,0.2)', border: '1px solid var(--border)',
    color: 'var(--text-primary)', outline: 'none', fontFamily: 'inherit',
  };

  return createPortal(
    <div style={{
      position: 'fixed', inset: 0, zIndex: 9999,
      background: 'rgba(0,0,0,0.6)',
      display: 'flex', alignItems: 'center', justifyContent: 'center',
    }} onClick={onClose}>
      <div style={{
        background: 'var(--bg-card)', borderRadius: 12, padding: 0,
        border: '1px solid var(--border)', width: 480, maxHeight: '75vh',
        display: 'flex', flexDirection: 'column', overflow: 'hidden',
      }} onClick={e => e.stopPropagation()}>
        <div style={{
          padding: '14px 16px', borderBottom: '1px solid var(--border-light)',
          display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        }}>
          <span style={{ fontSize: 15, fontWeight: 600, color: 'var(--text-primary)' }}>RAG 配置</span>
          <button onClick={onClose} style={{ background: 'none', border: 'none', color: 'var(--text-tertiary)', cursor: 'pointer', fontSize: 16 }}>✕</button>
        </div>

        <div style={{ flex: 1, overflowY: 'auto', padding: 16, display: 'flex', flexDirection: 'column', gap: 16 }}>
          <div>
            <div style={{ fontSize: 12, fontWeight: 500, color: 'var(--text-primary)', marginBottom: 6 }}>分块大小（tokens）</div>
            <input type="number" value={chunkSize} onChange={e => setChunkSize(Number(e.target.value))} style={inputStyle} />
          </div>
          <div>
            <div style={{ fontSize: 12, fontWeight: 500, color: 'var(--text-primary)', marginBottom: 6 }}>重叠大小（tokens）</div>
            <input type="number" value={chunkOverlap} onChange={e => setChunkOverlap(Number(e.target.value))} style={inputStyle} />
          </div>
          <div>
            <div style={{ fontSize: 12, fontWeight: 500, color: 'var(--text-primary)', marginBottom: 6 }}>搜索模式</div>
            <select value={searchMode} onChange={e => setSearchMode(e.target.value)} style={inputStyle}>
              <option value="default">向量检索</option>
              <option value="bm25">关键词检索</option>
              <option value="hybrid">混合检索</option>
            </select>
          </div>
          {searchMode === 'hybrid' && (
            <div>
              <div style={{ fontSize: 12, fontWeight: 500, color: 'var(--text-primary)', marginBottom: 6, display: 'flex', justifyContent: 'space-between' }}>
                <span>混合权重 (Alpha)</span>
                <span style={{ fontWeight: 400, color: 'var(--text-tertiary)' }}>{hybridAlpha.toFixed(2)}</span>
              </div>
              <input type="range" min="0" max="1" step="0.01" value={hybridAlpha}
                onChange={e => setHybridAlpha(Number(e.target.value))}
                style={{ width: '100%', accentColor: 'var(--accent-purple)' }}
              />
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 10, color: 'var(--text-tertiary)', marginTop: 4 }}>
                <span>纯关键词</span><span>纯向量</span>
              </div>
            </div>
          )}
          <div>
            <div style={{ fontSize: 12, fontWeight: 500, color: 'var(--text-primary)', marginBottom: 6 }}>相关性阈值</div>
            <input type="number" min="0" max="1" step="0.01" value={threshold}
              onChange={e => setThreshold(Number(e.target.value))} style={inputStyle} />
          </div>
          <div>
            <div style={{ fontSize: 12, fontWeight: 500, color: 'var(--text-primary)', marginBottom: 6 }}>返回结果数</div>
            <input type="number" min="1" max="50" value={documentCount}
              onChange={e => setDocumentCount(Number(e.target.value))} style={inputStyle} />
          </div>
        </div>

        <div style={{
          padding: '12px 16px', borderTop: '1px solid var(--border-light)',
          display: 'flex', justifyContent: 'flex-end', gap: 8,
        }}>
          <button onClick={onClose} style={{
            padding: '7px 16px', borderRadius: 6, fontSize: 12,
            background: 'transparent', border: '1px solid var(--border)',
            color: 'var(--text-secondary)', cursor: 'pointer', fontFamily: 'inherit',
          }}>取消</button>
          <button onClick={handleSave} disabled={saving} style={{
            padding: '7px 16px', borderRadius: 6, fontSize: 12, fontWeight: 500,
            background: 'var(--accent-purple)', border: 'none', color: '#fff',
            cursor: 'pointer', fontFamily: 'inherit', opacity: saving ? 0.5 : 1,
          }}>{saving ? '保存中...' : '保存'}</button>
        </div>
      </div>
    </div>,
    document.body
  );
}
