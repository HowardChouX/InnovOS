import { useState } from 'react';
import { createPortal } from 'react-dom';
import { useKnowledgeStore } from '../../store/useKnowledgeStore';
import { knowledgeApi } from '../../api/knowledge';

interface Props {
  open: boolean;
  onClose: () => void;
}

interface RecallResult {
  content: string;
  score: number;
  title?: string;
  chunkIndex?: number;
}

export function RecallTestPanel({ open, onClose }: Props) {
  const { selectedBaseId } = useKnowledgeStore();
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<RecallResult[]>([]);
  const [searching, setSearching] = useState(false);
  const [searched, setSearched] = useState(false);

  if (!open) return null;

  const handleSearch = async () => {
    if (!query.trim() || !selectedBaseId) return;
    setSearching(true);
    setSearched(true);
    try {
      const res = await knowledgeApi.search({ q: query, base_id: selectedBaseId, limit: 10 });
      setResults(res.data || []);
    } catch { setResults([]); } finally { setSearching(false); }
  };

  return createPortal(
    <div style={{
      position: 'fixed', inset: 0, zIndex: 9999,
      background: 'rgba(0,0,0,0.6)',
      display: 'flex', alignItems: 'center', justifyContent: 'center',
    }} onClick={onClose}>
      <div style={{
        background: 'var(--bg-card)', borderRadius: 12, padding: 0,
        border: '1px solid var(--border)', width: 560, maxHeight: '75vh',
        display: 'flex', flexDirection: 'column', overflow: 'hidden',
      }} onClick={e => e.stopPropagation()}>
        <div style={{
          padding: '14px 16px', borderBottom: '1px solid var(--border-light)',
          display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        }}>
          <span style={{ fontSize: 15, fontWeight: 600, color: 'var(--text-primary)' }}>召回测试</span>
          <button onClick={onClose} style={{ background: 'none', border: 'none', color: 'var(--text-tertiary)', cursor: 'pointer', fontSize: 16 }}>✕</button>
        </div>

        <div style={{ padding: '12px 16px', display: 'flex', gap: 8 }}>
          <input value={query} onChange={e => setQuery(e.target.value)} onKeyDown={e => e.key === 'Enter' && handleSearch()}
            placeholder="输入查询内容..."
            style={{
              flex: 1, padding: '8px 12px', borderRadius: 6, fontSize: 13,
              background: 'rgba(0,0,0,0.2)', border: '1px solid var(--border)',
              color: 'var(--text-primary)', outline: 'none', fontFamily: 'inherit',
            }} />
          <button onClick={handleSearch} disabled={searching || !query.trim()} style={{
            padding: '8px 16px', borderRadius: 6, fontSize: 12, fontWeight: 500,
            background: 'var(--accent-purple)', border: 'none', color: '#fff',
            cursor: 'pointer', fontFamily: 'inherit',
            opacity: searching || !query.trim() ? 0.5 : 1,
          }}>
            {searching ? '搜索中...' : '搜索'}
          </button>
        </div>

        <div style={{ flex: 1, overflowY: 'auto', padding: '0 16px 16px' }}>
          {searching && (
            <div style={{ textAlign: 'center', padding: 40, color: 'var(--text-tertiary)', fontSize: 12 }}>
              <i className="fa-solid fa-spinner fa-spin" style={{ marginRight: 6 }} />搜索中...
            </div>
          )}
          {!searching && searched && results.length === 0 && (
            <div style={{ textAlign: 'center', padding: 40, color: 'var(--text-tertiary)', fontSize: 12 }}>未找到相关结果</div>
          )}
          {!searching && results.length > 0 && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              <div style={{ fontSize: 11, color: 'var(--text-tertiary)', marginBottom: 4 }}>找到 {results.length} 条相关结果</div>
              {results.map((r, i) => (
                <div key={i} style={{
                  padding: '10px 12px', borderRadius: 8,
                  background: 'rgba(0,0,0,0.15)', border: '1px solid var(--border-light)',
                }}>
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 6 }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                      <span style={{
                        width: 20, height: 20, borderRadius: 4, fontSize: 10,
                        background: 'rgba(139,92,246,0.15)', color: 'var(--accent-purple)',
                        display: 'flex', alignItems: 'center', justifyContent: 'center', fontWeight: 600,
                      }}>{i + 1}</span>
                      {r.title && <span style={{ fontSize: 11, color: 'var(--text-secondary)' }}>{r.title}</span>}
                    </div>
                    <span style={{
                      fontSize: 11, fontFamily: 'monospace',
                      color: r.score > 0.8 ? 'var(--accent-green)' : r.score > 0.5 ? 'var(--accent-blue)' : 'var(--text-tertiary)',
                    }}>{(r.score * 100).toFixed(1)}%</span>
                  </div>
                  <div style={{
                    fontSize: 12, color: 'var(--text-secondary)', lineHeight: 1.6,
                    maxHeight: 80, overflow: 'hidden',
                  }}>{r.content}</div>
                </div>
              ))}
            </div>
          )}
          {!searched && !searching && (
            <div style={{ textAlign: 'center', padding: 40, color: 'var(--text-tertiary)', fontSize: 12 }}>输入查询内容测试检索效果</div>
          )}
        </div>
      </div>
    </div>,
    document.body
  );
}
