import { useState, useEffect, useCallback } from 'react';
import { knowledgeApi } from '../../api/knowledge';
import type { KnowledgeBaseListItem, KnowledgeSearchResult } from '../../types/knowledge';

interface SearchResultWithBase extends KnowledgeSearchResult {
  baseName: string;
  baseId: string;
}

export function KnowledgeQAPanel() {
  const [bases, setBases] = useState<KnowledgeBaseListItem[]>([]);
  const [selectedBaseIds, setSelectedBaseIds] = useState<Set<string>>(new Set());
  const [question, setQuestion] = useState('');
  const [searching, setSearching] = useState(false);
  const [results, setResults] = useState<SearchResultWithBase[]>([]);
  const [hasSearched, setHasSearched] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    knowledgeApi.listBases(1, 100).then((res) => {
      const items = res.data?.items || [];
      setBases(items);
      if (items.length > 0) {
        setSelectedBaseIds(new Set([items[0].id]));
      }
    }).catch(() => setBases([]));
  }, []);

  const toggleBase = useCallback((id: string) => {
    setSelectedBaseIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
      }
      return next;
    });
  }, []);

  const handleSearch = useCallback(async () => {
    const q = question.trim();
    if (!q) return;
    if (selectedBaseIds.size === 0) {
      setError('请至少选择一个知识库');
      return;
    }

    setSearching(true);
    setError('');
    setHasSearched(true);

    try {
      const baseIdArr = Array.from(selectedBaseIds);
      const baseMap = new Map(bases.map((b) => [b.id, b.name]));

      // 并行搜索所有选中知识库
      const searches = baseIdArr.map((baseId) =>
        knowledgeApi.search({ q, base_id: baseId, limit: 5 }).then((res) => ({
          baseId,
          baseName: baseMap.get(baseId) || '未知',
          items: (res.data || []) as KnowledgeSearchResult[],
        }))
      );

      const allResults = await Promise.all(searches);

      // 合并并按分数降序排列
      const merged: SearchResultWithBase[] = [];
      for (const sr of allResults) {
        for (const item of sr.items) {
          merged.push({ ...item, baseName: sr.baseName, baseId: sr.baseId });
        }
      }
      merged.sort((a, b) => b.score - a.score);
      setResults(merged);
    } catch (err) {
      setError('搜索失败，请稍后重试');
      console.error(err);
    } finally {
      setSearching(false);
    }
  }, [question, selectedBaseIds, bases]);

  return (
    <div className="card">
      {/* Header */}
      <div style={{ marginBottom: 14 }}>
        <div className="card-title" style={{ marginBottom: 4 }}>
          知识库问答
        </div>
        <div style={{ fontSize: 12, color: 'var(--text-secondary)' }}>
          从知识库中检索相关内容作为分析参考
        </div>
      </div>

      {/* Knowledge base selector */}
      <div style={{ marginBottom: 12 }}>
        <div style={{ fontSize: 12, color: 'var(--text-secondary)', marginBottom: 8 }}>
          选择知识库：
        </div>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
          {bases.map((base) => {
            const active = selectedBaseIds.has(base.id);
            return (
              <button
                key={base.id}
                onClick={() => toggleBase(base.id)}
                style={{
                  display: 'flex', alignItems: 'center', gap: 5,
                  padding: '4px 10px', borderRadius: 14, cursor: 'pointer',
                  fontSize: 12, fontFamily: 'inherit', border: '1px solid',
                  background: active ? 'var(--accent)' : 'transparent',
                  color: active ? '#fff' : 'var(--text-secondary)',
                  borderColor: active ? 'var(--accent)' : 'var(--border)',
                  transition: 'all 0.15s',
                }}
              >
                <i
                  className={`fa-solid ${active ? 'fa-check-circle' : 'fa-circle'}`}
                  style={{ fontSize: 10 }}
                />
                {base.name}
                <span style={{ fontSize: 10, opacity: 0.7 }}>
                  ({base.itemCount ?? base.documentCount ?? 0})
                </span>
              </button>
            );
          })}
        </div>
      </div>

      {/* Question input */}
      <div style={{ display: 'flex', gap: 8 }}>
        <input
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
          placeholder="输入您的问题..."
          disabled={searching}
          style={{
            flex: 1,
            background: 'rgba(0,0,0,0.3)', border: '1px solid var(--border)',
            borderRadius: 8, padding: '8px 12px',
            fontSize: 13, color: 'var(--text-primary)',
            outline: 'none', fontFamily: 'inherit',
          }}
        />
        <button
          onClick={handleSearch}
          disabled={searching || !question.trim() || selectedBaseIds.size === 0}
          style={{
            display: 'flex', alignItems: 'center', gap: 6,
            background: searching ? 'var(--text-tertiary)' : 'var(--accent)',
            border: 'none', color: '#fff', padding: '8px 16px',
            borderRadius: 8, cursor: searching ? 'not-allowed' : 'pointer',
            fontSize: 13, fontFamily: 'inherit',
          }}
        >
          {searching ? (
            <i className="fa-solid fa-circle-notch fa-spin" style={{ fontSize: 12 }} />
          ) : (
            <i className="fa-solid fa-magnifying-glass" style={{ fontSize: 12 }} />
          )}
          {searching ? '搜索中...' : '搜索'}
        </button>
      </div>

      {/* Error */}
      {error && (
        <div style={{ marginTop: 8, fontSize: 12, color: 'var(--accent-red)' }}>
          <i className="fa-solid fa-triangle-exclamation" style={{ marginRight: 4 }} />
          {error}
        </div>
      )}

      {/* Results */}
      {hasSearched && !searching && (
        <div style={{ marginTop: 14 }}>
          <div style={{
            display: 'flex', justifyContent: 'space-between', alignItems: 'center',
            marginBottom: 10, fontSize: 12, color: 'var(--text-secondary)',
          }}>
            <span>
              搜索结果 ({results.length} 条)
            </span>
            {results.length > 0 && (
              <button
                onClick={() => { setResults([]); setHasSearched(false); setQuestion(''); }}
                style={{
                  background: 'transparent', border: 'none', cursor: 'pointer',
                  fontSize: 12, color: 'var(--text-tertiary)', fontFamily: 'inherit',
                }}
              >
                清除
              </button>
            )}
          </div>

          {results.length === 0 ? (
            <div style={{
              textAlign: 'center', padding: '20px 0',
              fontSize: 13, color: 'var(--text-tertiary)',
            }}>
              <i className="fa-solid fa-file-circle-exclamation" style={{ fontSize: 24, display: 'block', marginBottom: 8 }} />
              未找到相关结果
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              {results.map((r, i) => (
                <div
                  key={`${r.chunkId}-${i}`}
                  style={{
                    background: 'rgba(0,0,0,0.2)', borderRadius: 8,
                    padding: '10px 12px', border: '1px solid var(--border)',
                  }}
                >
                  {/* Result header */}
                  <div style={{
                    display: 'flex', justifyContent: 'space-between',
                    alignItems: 'center', marginBottom: 6,
                  }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                      <span style={{
                        display: 'inline-block', padding: '1px 6px', borderRadius: 4,
                        fontSize: 11, fontWeight: 600,
                        background: r.score > 0.8 ? 'rgba(34,197,94,0.15)' : 'rgba(234,179,8,0.15)',
                        color: r.score > 0.8 ? 'rgb(34,197,94)' : 'rgb(234,179,8)',
                      }}>
                        {Math.round(r.score * 100)}%
                      </span>
                      <span style={{ fontSize: 11, color: 'var(--accent)' }}>
                        {r.baseName}
                      </span>
                    </div>
                    <span style={{ fontSize: 10, color: 'var(--text-tertiary)' }}>
                      #{r.rank}
                    </span>
                  </div>

                  {/* Content preview */}
                  <div style={{
                    fontSize: 12, color: 'var(--text-secondary)',
                    lineHeight: 1.5, maxHeight: 60, overflow: 'hidden',
                    display: '-webkit-box', WebkitLineClamp: 3, WebkitBoxOrient: 'vertical',
                  }}>
                    {r.pageContent}
                  </div>

                  {/* Source info */}
                  <div style={{ marginTop: 4, fontSize: 10, color: 'var(--text-tertiary)' }}>
                    {r.metadata?.source && (
                      <span>来源: {r.metadata.source}</span>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
