import { useState, useEffect } from 'react';
import { createPortal } from 'react-dom';
import { useKnowledgeStore } from '../../store/useKnowledgeStore';
import { knowledgeApi } from '../../api/knowledge';

interface Props {
  open: boolean;
  onClose: () => void;
}

interface ModelOption {
  id: string;
  providerId: string;
  providerName: string;
  modelId: string;
  label: string;
}

export default function CreateKnowledgeBaseDialog({ open, onClose }: Props) {
  const { createBase } = useKnowledgeStore();

  const [name, setName] = useState('');
  const [embeddingModelId, setEmbeddingModelId] = useState('');
  const [dimensions, setDimensions] = useState('');
  const [topK, setTopK] = useState(30);
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [documentProcessor, setDocumentProcessor] = useState('');
  const [rerankModelId, setRerankModelId] = useState('');
  const [chunkSize, setChunkSize] = useState('');
  const [chunkOverlap, setChunkOverlap] = useState('');
  const [threshold, setThreshold] = useState('');

  const [embeddingModels, setEmbeddingModels] = useState<ModelOption[]>([]);
  const [rerankModels, setRerankModels] = useState<ModelOption[]>([]);
  const [loadingModels, setLoadingModels] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    if (open) {
      setName(''); setEmbeddingModelId(''); setDimensions('');
      setTopK(30); setShowAdvanced(false);
      setDocumentProcessor(''); setRerankModelId('');
      setChunkSize(''); setChunkOverlap(''); setThreshold('');
      setError('');
      loadModels();
    }
  }, [open]);

  const loadModels = async () => {
    setLoadingModels(true);
    try {
      const [embRes, rerankRes] = await Promise.all([
        knowledgeApi.listEmbeddingModels(),
        knowledgeApi.listRerankModels(),
      ]);
      setEmbeddingModels(embRes.data || []);
      setRerankModels(rerankRes.data || []);
    } catch {
      setEmbeddingModels([]);
      setRerankModels([]);
    } finally {
      setLoadingModels(false);
    }
  };

  if (!open) return null;

  const handleSubmit = async () => {
    if (!name.trim()) { setError('请输入知识库名称'); return; }
    if (!embeddingModelId) { setError('请选择嵌入模型'); return; }
    setError('');
    setSubmitting(true);
    try {
      await createBase(name.trim(), undefined, {
        embeddingModelId,
        dimensions: dimensions ? Number(dimensions) : 1024,
        documentCount: topK,
        rerankModelId: rerankModelId || undefined,
        chunkSize: chunkSize ? Number(chunkSize) : undefined,
        chunkOverlap: chunkOverlap ? Number(chunkOverlap) : undefined,
        threshold: threshold ? Number(threshold) : undefined,
      });
      onClose();
    } catch (e: any) {
      setError(e?.message || '创建失败');
    } finally {
      setSubmitting(false);
    }
  };

  const inputStyle: React.CSSProperties = {
    width: '100%', padding: '8px 12px', borderRadius: 6, fontSize: 13,
    background: 'rgba(0,0,0,0.2)', border: '1px solid var(--border)',
    color: 'var(--text-primary)', outline: 'none', fontFamily: 'inherit',
    boxSizing: 'border-box',
  };

  const selectStyle: React.CSSProperties = {
    ...inputStyle, cursor: 'pointer', appearance: 'none' as const,
    backgroundImage: `url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='12' height='12' viewBox='0 0 12 12'%3E%3Cpath fill='%2364748b' d='M2 4l4 4 4-4'/%3E%3C/svg%3E")`,
    backgroundRepeat: 'no-repeat', backgroundPosition: 'right 10px center', paddingRight: 30,
  };

  const labelStyle: React.CSSProperties = {
    fontSize: 13, color: 'var(--text-primary)', fontWeight: 500,
    display: 'flex', alignItems: 'center', gap: 6, marginBottom: 8,
  };

  const hintIcon: React.CSSProperties = {
    fontSize: 9, color: 'var(--text-tertiary)', cursor: 'help',
    width: 14, height: 14, borderRadius: '50%',
    border: '1px solid var(--text-tertiary)', display: 'inline-flex',
    alignItems: 'center', justifyContent: 'center', lineHeight: 1,
  };

  return createPortal(
    <div style={{
      position: 'fixed', inset: 0, zIndex: 9999,
      background: 'rgba(0,0,0,0.5)',
      display: 'flex', alignItems: 'center', justifyContent: 'center',
    }} onClick={onClose}>
      <div style={{
        width: 'min(520px, 90vw)', maxHeight: '85vh',
        background: 'var(--bg-card)', borderRadius: 12, border: '1px solid var(--border)',
        display: 'flex', flexDirection: 'column', overflow: 'hidden',
      }} onClick={e => e.stopPropagation()}>
        {/* Header */}
        <div style={{
          padding: '16px 20px', borderBottom: '1px solid var(--border-light)',
          display: 'flex', justifyContent: 'space-between', alignItems: 'center',
        }}>
          <span style={{ fontSize: 16, fontWeight: 600, color: 'var(--text-primary)' }}>添加知识库</span>
          <button onClick={onClose} style={{
            background: 'none', border: 'none', color: 'var(--text-tertiary)',
            cursor: 'pointer', fontSize: 16, padding: 4,
          }}>✕</button>
        </div>

        {/* Body */}
        <div style={{ flex: 1, overflowY: 'auto', padding: '20px' }}>
          {/* 名称 */}
          <div style={{ marginBottom: 20 }}>
            <div style={labelStyle}>名称</div>
            <input
              value={name} onChange={e => setName(e.target.value)}
              placeholder="名称" autoFocus
              style={inputStyle}
              onKeyDown={e => { if (e.key === 'Enter') handleSubmit(); }}
            />
          </div>

          {/* 嵌入模型 */}
          <div style={{ marginBottom: 20 }}>
            <div style={labelStyle}>
              嵌入模型 <span style={hintIcon}>i</span>
            </div>
            <select
              value={embeddingModelId}
              onChange={e => setEmbeddingModelId(e.target.value)}
              style={selectStyle}
            >
              <option value="">{loadingModels ? '加载中...' : '未选择模型'}</option>
              {embeddingModels.map(m => (
                <option key={m.id} value={m.id}>{m.label}</option>
              ))}
            </select>
          </div>

          {/* 嵌入维度 */}
          <div style={{ marginBottom: 20 }}>
            <div style={labelStyle}>
              嵌入维度 <span style={hintIcon}>i</span>
            </div>
            <div style={{ display: 'flex', gap: 8 }}>
              <input
                value={dimensions} onChange={e => setDimensions(e.target.value)}
                placeholder="留空表示不设置"
                style={inputStyle}
              />
              <button style={{
                width: 36, height: 36, flexShrink: 0, borderRadius: 6,
                background: 'rgba(0,0,0,0.2)', border: '1px solid var(--border)',
                color: 'var(--text-tertiary)', cursor: 'pointer', fontSize: 13,
                display: 'flex', alignItems: 'center', justifyContent: 'center',
              }}>
                <i className="fa-solid fa-rotate" />
              </button>
            </div>
          </div>

          {/* 请求文档片段数量 */}
          <div style={{ marginBottom: 20 }}>
            <div style={labelStyle}>
              请求文档片段数量 <span style={hintIcon}>i</span>
            </div>
            <input
              type="range" min={1} max={50} value={topK}
              onChange={e => setTopK(Number(e.target.value))}
              style={{ width: '100%', accentColor: 'var(--accent-purple)' }}
            />
            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11, color: 'var(--text-tertiary)', marginTop: 4 }}>
              <span>1</span>
              <span style={{ color: topK === 30 ? 'var(--text-secondary)' : 'var(--text-tertiary)' }}>
                {topK === 30 ? '默认' : topK}
              </span>
              <span>30</span>
              <span>50</span>
            </div>
          </div>

          {/* Divider */}
          <div style={{ height: 1, background: 'var(--border-light)', margin: '8px 0 16px' }} />

          {/* 高级设置（折叠） */}
          {showAdvanced && (
            <>
              {/* 文档处理 */}
              <div style={{ marginBottom: 20 }}>
                <div style={labelStyle}>
                  文档处理 <span style={hintIcon}>i</span>
                </div>
                <select value={documentProcessor} onChange={e => setDocumentProcessor(e.target.value)} style={selectStyle}>
                  <option value="">选择一个文档处理服务商</option>
                </select>
              </div>

              {/* 重排模型 */}
              <div style={{ marginBottom: 20 }}>
                <div style={labelStyle}>
                  重排模型 <span style={hintIcon}>i</span>
                </div>
                <select value={rerankModelId} onChange={e => setRerankModelId(e.target.value)} style={selectStyle}>
                  <option value="">{loadingModels ? '加载中...' : '没有模型'}</option>
                  {rerankModels.map(m => (
                    <option key={m.id} value={m.id}>{m.label}</option>
                  ))}
                </select>
              </div>

              {/* 分段大小 */}
              <div style={{ marginBottom: 20 }}>
                <div style={labelStyle}>
                  分段大小 <span style={hintIcon}>i</span>
                </div>
                <input
                  value={chunkSize} onChange={e => setChunkSize(e.target.value)}
                  placeholder="默认值（不建议修改）"
                  style={inputStyle}
                />
              </div>

              {/* 重叠大小 */}
              <div style={{ marginBottom: 20 }}>
                <div style={labelStyle}>
                  重叠大小 <span style={hintIcon}>i</span>
                </div>
                <input
                  value={chunkOverlap} onChange={e => setChunkOverlap(e.target.value)}
                  placeholder="默认值（不建议修改）"
                  style={inputStyle}
                />
              </div>

              {/* 匹配度阈值 */}
              <div style={{ marginBottom: 20 }}>
                <div style={labelStyle}>
                  匹配度阈值 <span style={hintIcon}>i</span>
                </div>
                <input
                  value={threshold} onChange={e => setThreshold(e.target.value)}
                  placeholder="未设置"
                  style={inputStyle}
                />
              </div>

              {/* Warning */}
              <div style={{
                padding: '10px 14px', borderRadius: 8,
                background: 'rgba(251,191,36,0.1)', border: '1px solid rgba(251,191,36,0.3)',
                fontSize: 12, color: '#fbbf24', display: 'flex', alignItems: 'center', gap: 8,
              }}>
                <i className="fa-solid fa-triangle-exclamation" style={{ fontSize: 14 }} />
                分段大小和重叠大小修改只针对新添加的内容有效
              </div>
            </>
          )}

          {error && (
            <div style={{ fontSize: 12, color: 'var(--accent-red)', marginTop: 8 }}>{error}</div>
          )}
        </div>

        {/* Footer */}
        <div style={{
          padding: '12px 20px', borderTop: '1px solid var(--border-light)',
          display: 'flex', justifyContent: 'space-between', alignItems: 'center',
        }}>
          <button
            onClick={() => setShowAdvanced(!showAdvanced)}
            style={{
              padding: '7px 14px', borderRadius: 6, fontSize: 12,
              background: 'transparent', border: '1px solid var(--border)',
              color: 'var(--text-secondary)', cursor: 'pointer', fontFamily: 'inherit',
              display: 'flex', alignItems: 'center', gap: 6,
            }}
          >
            <i className={`fa-solid fa-chevron-${showAdvanced ? 'up' : 'down'}`} style={{ fontSize: 9 }} />
            高级设置
          </button>
          <div style={{ display: 'flex', gap: 8 }}>
            <button onClick={onClose} style={{
              padding: '7px 20px', borderRadius: 6, fontSize: 13,
              background: 'transparent', border: '1px solid var(--border)',
              color: 'var(--text-secondary)', cursor: 'pointer', fontFamily: 'inherit',
            }}>取 消</button>
            <button onClick={handleSubmit} disabled={submitting || !name.trim() || !embeddingModelId} style={{
              padding: '7px 20px', borderRadius: 6, fontSize: 13, fontWeight: 500,
              background: (name.trim() && embeddingModelId) ? 'var(--accent-purple)' : 'var(--border)',
              border: 'none', color: '#fff', cursor: 'pointer', fontFamily: 'inherit',
              opacity: submitting ? 0.7 : 1,
            }}>{submitting ? '创建中...' : '确 认'}</button>
          </div>
        </div>
      </div>
    </div>,
    document.body
  );
}
