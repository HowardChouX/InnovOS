import { useState, useEffect, useRef } from 'react';
import { patentsApi } from '../../api/patents';
import type { Patent } from '../../types/patent';
import type { SemanticResult } from '../../api/patents';

function PatentDetailModal({ patent, onClose }: { patent: Patent; onClose: () => void }) {
  if (!patent) return null;

  return (
    <div style={{
      position: 'fixed', top: 0, left: 0, right: 0, bottom: 0,
      background: 'rgba(0,0,0,0.6)', zIndex: 100,
      display: 'flex', alignItems: 'center', justifyContent: 'center',
    }} onClick={onClose}>
      <div style={{
        background: 'var(--bg-card)', borderRadius: 12, border: '1px solid var(--border)',
        width: 600, maxHeight: '80vh', overflow: 'auto', padding: 24,
      }} onClick={(e) => e.stopPropagation()}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
          <h3 style={{ fontSize: 16, fontWeight: 600, color: 'var(--text-primary)', margin: 0 }}>
            专利详情
          </h3>
          <button onClick={onClose} style={{
            background: 'none', border: 'none', color: 'var(--text-tertiary)',
            cursor: 'pointer', fontSize: 16,
          }}>
            <i className="fa-solid fa-xmark" />
          </button>
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          <div>
            <div style={{ fontSize: 11, color: 'var(--text-tertiary)', marginBottom: 4 }}>专利名称</div>
            <div style={{ fontSize: 14, fontWeight: 600, color: 'var(--text-primary)', lineHeight: 1.5 }}>
              {patent.title}
            </div>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
            <div>
              <div style={{ fontSize: 11, color: 'var(--text-tertiary)', marginBottom: 4 }}>专利号</div>
              <div style={{ fontSize: 13, color: 'var(--text-secondary)' }}>{patent.patentNumber}</div>
            </div>
            <div>
              <div style={{ fontSize: 11, color: 'var(--text-tertiary)', marginBottom: 4 }}>申请日</div>
              <div style={{ fontSize: 13, color: 'var(--text-secondary)' }}>{patent.filingDate?.slice(0, 10)}</div>
            </div>
          </div>

          <div>
            <div style={{ fontSize: 11, color: 'var(--text-tertiary)', marginBottom: 4 }}>申请人</div>
            <div style={{ fontSize: 13, color: 'var(--text-secondary)' }}>
              {(patent.applicants || []).join('、')}
            </div>
          </div>

          <div>
            <div style={{ fontSize: 11, color: 'var(--text-tertiary)', marginBottom: 4 }}>发明人</div>
            <div style={{ fontSize: 13, color: 'var(--text-secondary)' }}>
              {(patent.inventors || []).join('、')}
            </div>
          </div>

          <div>
            <div style={{ fontSize: 11, color: 'var(--text-tertiary)', marginBottom: 4 }}>IPC分类号</div>
            <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
              {(patent.ipcCodes || []).map((code) => (
                <span key={code} style={{
                  fontSize: 11, padding: '3px 8px', borderRadius: 4,
                  background: 'rgba(59,130,246,0.1)', color: 'var(--accent-blue)',
                  border: '1px solid rgba(59,130,246,0.2)',
                }}>
                  {code}
                </span>
              ))}
            </div>
          </div>

          <div>
            <div style={{ fontSize: 11, color: 'var(--text-tertiary)', marginBottom: 4 }}>相关度</div>
            <div style={{ fontSize: 13, color: 'var(--accent-green)', fontWeight: 600 }}>
              {patent.relevanceScore}%
            </div>
          </div>

          <div>
            <div style={{ fontSize: 11, color: 'var(--text-tertiary)', marginBottom: 4 }}>摘要</div>
            <div style={{ fontSize: 13, color: 'var(--text-secondary)', lineHeight: 1.6 }}>
              {patent.abstract || '暂无摘要'}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

export function PatentSearchPage() {
  const [query, setQuery] = useState('');
  const [ipcCode, setIpcCode] = useState('');
  const [applicant, setApplicant] = useState('');
  const [sortBy, setSortBy] = useState('relevance');
  const [patents, setPatents] = useState<Patent[]>([]);
  const [loading, setLoading] = useState(false);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [pageSize] = useState(20);
  const [selectedPatent, setSelectedPatent] = useState<Patent | null>(null);
  const [showFilters, setShowFilters] = useState(false);
  const [semanticMode, setSemanticMode] = useState(false);
  const [semanticResults, setSemanticResults] = useState<SemanticResult[]>([]);
  const initialized = useRef(false);

  const totalPages = Math.ceil(total / pageSize);

  const fetchPatents = async (pageNum = 1) => {
    setLoading(true);
    try {
      const res = await patentsApi.search({
        q: query,
        page: pageNum,
        page_size: pageSize,
        ...(ipcCode ? { ipc_code: ipcCode } : {}),
        ...(applicant ? { applicant } : {}),
        sort_by: sortBy,
      });
      setPatents(res.data);
      setTotal(res.total);
      setPage(pageNum);
    } catch {
      // ignore
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (!initialized.current) {
      initialized.current = true;
      fetchPatents(1);
    }
  }, []);

  const handleSearch = () => {
    if (semanticMode) {
      setLoading(true);
      patentsApi.semanticSearch(query, 20).then(res => {
        setSemanticResults(res.data);
        setTotal(res.total);
        setLoading(false);
      }).catch(() => setLoading(false));
    } else {
      fetchPatents(1);
    }
  };

  const handlePageChange = (newPage: number) => {
    if (newPage >= 1 && newPage <= totalPages) {
      fetchPatents(newPage);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') {
      handleSearch();
    }
  };

  return (
    <div className="card" style={{ display: 'flex', flexDirection: 'column', height: '100%', minHeight: 0 }}>
      <div className="card-title" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div>
          <i className="fa-solid fa-file-lines" style={{ marginRight: 8, color: 'var(--accent-cyan)' }} />
          专利检索
        </div>
        <span style={{ fontSize: 12, color: 'var(--text-tertiary)' }}>
          共 {total.toLocaleString()} 条专利
        </span>
      </div>

      {/* 搜索区域 */}
      <div style={{ marginBottom: 16 }}>
        <div style={{ display: 'flex', gap: 8, marginBottom: 8 }}>
          <div style={{ position: 'relative', flex: 1 }}>
            <i className="fa-solid fa-magnifying-glass" style={{
              position: 'absolute', left: 10, top: '50%', transform: 'translateY(-50%)',
              fontSize: 12, color: 'var(--text-tertiary)',
            }} />
            <input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="搜索专利标题或摘要..."
              style={{
                width: '100%', padding: '8px 10px 8px 32px', borderRadius: 6,
                background: 'rgba(0,0,0,0.2)', border: '1px solid var(--border)',
                color: 'var(--text-primary)', fontSize: 13, outline: 'none', fontFamily: 'inherit',
              }}
            />
          </div>
          <button
            onClick={() => setShowFilters(!showFilters)}
            style={{
              padding: '8px 14px', borderRadius: 6,
              background: showFilters ? 'rgba(59,130,246,0.15)' : 'rgba(0,0,0,0.2)',
              border: '1px solid var(--border)',
              color: showFilters ? 'var(--accent-blue)' : 'var(--text-secondary)',
              cursor: 'pointer', fontSize: 13, fontFamily: 'inherit',
            }}
          >
            <i className="fa-solid fa-filter" style={{ marginRight: 4 }} />
            筛选
          </button>
          <button
            onClick={handleSearch}
            style={{
              padding: '8px 20px', borderRadius: 6,
              background: 'var(--accent)', border: 'none',
              color: '#fff', cursor: 'pointer', fontSize: 13, fontFamily: 'inherit',
            }}
          >
          搜索
            </button>
            <button
              onClick={() => setSemanticMode(!semanticMode)}
              style={{
                padding: '8px 14px', borderRadius: 6,
                background: semanticMode ? 'rgba(139,92,246,0.15)' : 'rgba(0,0,0,0.2)',
                border: '1px solid var(--border-light)',
                color: semanticMode ? 'var(--accent-purple)' : 'var(--text-tertiary)',
                cursor: 'pointer', fontSize: 12, fontFamily: 'inherit',
              }}
              title="语义搜索基于AI理解含义查找相似专利，关键词搜索基于文字匹配">
              <i className="fa-solid fa-wand-magic-sparkles" style={{ marginRight: 4 }} />
              语义
            </button>
        </div>

        {/* 高级筛选 */}
        {showFilters && (
          <div style={{
            display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 8,
            padding: 12, background: 'rgba(0,0,0,0.15)', borderRadius: 6,
            border: '1px solid var(--border-light)',
          }}>
            <div>
              <div style={{ fontSize: 10, color: 'var(--text-tertiary)', marginBottom: 4 }}>IPC分类号</div>
              <input
                value={ipcCode}
                onChange={(e) => setIpcCode(e.target.value)}
                placeholder="如: H01M"
                style={{
                  width: '100%', padding: '6px 10px', borderRadius: 4,
                  background: 'rgba(0,0,0,0.2)', border: '1px solid var(--border-light)',
                  color: 'var(--text-primary)', fontSize: 12, outline: 'none', fontFamily: 'inherit',
                }}
              />
            </div>
            <div>
              <div style={{ fontSize: 10, color: 'var(--text-tertiary)', marginBottom: 4 }}>申请人</div>
              <input
                value={applicant}
                onChange={(e) => setApplicant(e.target.value)}
                placeholder="申请人名称"
                style={{
                  width: '100%', padding: '6px 10px', borderRadius: 4,
                  background: 'rgba(0,0,0,0.2)', border: '1px solid var(--border-light)',
                  color: 'var(--text-primary)', fontSize: 12, outline: 'none', fontFamily: 'inherit',
                }}
              />
            </div>
            <div>
              <div style={{ fontSize: 10, color: 'var(--text-tertiary)', marginBottom: 4 }}>排序方式</div>
              <select
                value={sortBy}
                onChange={(e) => setSortBy(e.target.value)}
                style={{
                  width: '100%', padding: '6px 10px', borderRadius: 4,
                  background: 'rgba(0,0,0,0.2)', border: '1px solid var(--border-light)',
                  color: 'var(--text-primary)', fontSize: 12, outline: 'none', fontFamily: 'inherit',
                }}
              >
                <option value="relevance">按相关度</option>
                <option value="date">按申请日期</option>
                <option value="score">按评分</option>
              </select>
            </div>
          </div>
        )}
      </div>

      {/* 专利列表 */}
      <div style={{ flex: 1, overflow: 'auto', minHeight: 0 }}>
        {loading ? (
          <div style={{ padding: '40px 0', textAlign: 'center' }}>
            <i className="fa-solid fa-circle-notch fa-spin" style={{ fontSize: 24, color: 'var(--accent-blue)' }} />
            <div style={{ fontSize: 12, color: 'var(--text-tertiary)', marginTop: 8 }}>加载中...</div>
          </div>
        ) : semanticMode && semanticResults.length > 0 ? (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            {semanticResults.map((r, i) => (
              <div key={r.itemId} style={{
                display: 'flex', alignItems: 'flex-start', gap: 12,
                padding: '12px 14px', borderRadius: 8,
                background: 'rgba(139,92,246,0.08)', border: '1px solid rgba(139,92,246,0.2)',
                cursor: 'pointer', transition: 'all 0.15s',
              }}
                onMouseOver={(e) => { e.currentTarget.style.background = 'rgba(139,92,246,0.15)'; }}
                onMouseOut={(e) => { e.currentTarget.style.background = 'rgba(139,92,246,0.08)'; }}
                onClick={() => setSelectedPatent({
                  id: r.patentId, title: r.title || '', abstract: r.text,
                  patentNumber: r.patentNumber || '', filingDate: '', publicationDate: '',
                  applicants: [], inventors: [], ipcCodes: [], relevanceScore: Math.round(r.score * 100),
                  publicationNumber: '', priorityNumber: '', claims: '', description: '', pdfPath: '', created_at: '',
                } as Patent)}>
                <span style={{
                  width: 28, height: 28, borderRadius: '50%', flexShrink: 0,
                  background: 'rgba(139,92,246,0.15)', border: '1px solid rgba(139,92,246,0.3)',
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  fontSize: 11, fontWeight: 600, color: 'var(--accent-purple)',
                }}>{i + 1}</span>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-primary)', marginBottom: 4 }}>
                    {r.title || `专利 #${r.patentId}`}
                  </div>
                  <div style={{ fontSize: 11, color: 'var(--text-secondary)', lineHeight: 1.5, marginBottom: 4 }}>
                    {r.text.slice(0, 200)}{r.text.length > 200 ? '...' : ''}
                  </div>
                  {r.patentNumber && (
                    <div style={{ fontSize: 10, color: 'var(--text-tertiary)' }}>
                      专利号: {r.patentNumber}
                    </div>
                  )}
                </div>
                <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', flexShrink: 0 }}>
                  <span style={{ fontSize: 12, fontWeight: 600, color: 'var(--accent-purple)' }}>
                    {Math.round(r.score * 100)}%
                  </span>
                  <span style={{ fontSize: 9, color: 'var(--text-tertiary)' }}>相似度</span>
                </div>
              </div>
            ))}
          </div>
        ) : patents.length === 0 && !semanticMode ? (
          <div style={{ padding: '40px 0', textAlign: 'center', color: 'var(--text-tertiary)', fontSize: 13 }}>
            <i className="fa-solid fa-inbox" style={{ fontSize: 32, marginBottom: 12, display: 'block', opacity: 0.3 }} />
            暂无专利数据
          </div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            {patents.map((patent, index) => (
              <div
                key={patent.id}
                onClick={() => setSelectedPatent(patent)}
                style={{
                  display: 'flex', alignItems: 'flex-start', gap: 12,
                  padding: '12px 14px', borderRadius: 8,
                  background: 'rgba(0,0,0,0.15)', border: '1px solid var(--border-light)',
                  cursor: 'pointer', transition: 'all 0.15s',
                }}
                onMouseOver={(e) => {
                  e.currentTarget.style.background = 'rgba(0,0,0,0.25)';
                  e.currentTarget.style.borderColor = 'var(--border)';
                }}
                onMouseOut={(e) => {
                  e.currentTarget.style.background = 'rgba(0,0,0,0.15)';
                  e.currentTarget.style.borderColor = 'var(--border-light)';
                }}
              >
                <span style={{
                  width: 28, height: 28, borderRadius: '50%', flexShrink: 0,
                  background: 'rgba(59,130,246,0.15)', border: '1px solid rgba(59,130,246,0.3)',
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  fontSize: 11, fontWeight: 600, color: 'var(--accent-blue)',
                }}>
                  {(page - 1) * pageSize + index + 1}
                </span>

                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{
                    fontSize: 13, fontWeight: 600, color: 'var(--text-primary)',
                    marginBottom: 4, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
                  }}>
                    {patent.title}
                  </div>
                  <div style={{ fontSize: 11, color: 'var(--text-secondary)', marginBottom: 4, lineHeight: 1.5 }}>
                    {patent.abstract?.slice(0, 120) || '暂无摘要'}
                    {patent.abstract?.length > 120 ? '...' : ''}
                  </div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 10, fontSize: 10, color: 'var(--text-tertiary)' }}>
                    <span>申请号: {patent.patentNumber}</span>
                    <span>申请日: {patent.filingDate?.slice(0, 10)}</span>
                    <div style={{ display: 'flex', gap: 4 }}>
                      {(patent.ipcCodes || []).slice(0, 3).map((code) => (
                        <span key={code} style={{
                          padding: '1px 6px', borderRadius: 3,
                          background: 'rgba(59,130,246,0.1)', color: 'var(--accent-blue)',
                          border: '1px solid rgba(59,130,246,0.2)',
                        }}>
                          {code}
                        </span>
                      ))}
                    </div>
                  </div>
                </div>

                <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: 4, flexShrink: 0 }}>
                  <span style={{ fontSize: 12, fontWeight: 600, color: 'var(--accent-green)' }}>
                    {patent.relevanceScore}%
                  </span>
                  <span style={{ fontSize: 9, color: 'var(--text-tertiary)' }}>相关度</span>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* 分页 */}
      {totalPages > 1 && (
        <div style={{
          display: 'flex', justifyContent: 'center', alignItems: 'center', gap: 8,
          marginTop: 16, paddingTop: 12, borderTop: '1px solid var(--border-light)',
        }}>
          <button
            onClick={() => handlePageChange(page - 1)}
            disabled={page <= 1}
            style={{
              padding: '4px 10px', borderRadius: 4,
              background: 'rgba(0,0,0,0.2)', border: '1px solid var(--border-light)',
              color: page <= 1 ? 'var(--text-tertiary)' : 'var(--text-secondary)',
              cursor: page <= 1 ? 'not-allowed' : 'pointer', fontSize: 11, fontFamily: 'inherit',
            }}
          >
            <i className="fa-solid fa-chevron-left" />
          </button>

          <div style={{ display: 'flex', gap: 4 }}>
            {Array.from({ length: Math.min(5, totalPages) }, (_, i) => {
              const pageNum = i + 1;
              return (
                <button
                  key={pageNum}
                  onClick={() => handlePageChange(pageNum)}
                  style={{
                    width: 28, height: 28, borderRadius: 4,
                    background: pageNum === page ? 'var(--accent)' : 'rgba(0,0,0,0.2)',
                    border: '1px solid var(--border-light)',
                    color: pageNum === page ? '#fff' : 'var(--text-secondary)',
                    cursor: 'pointer', fontSize: 11, fontFamily: 'inherit',
                  }}
                >
                  {pageNum}
                </button>
              );
            })}
          </div>

          <button
            onClick={() => handlePageChange(page + 1)}
            disabled={page >= totalPages}
            style={{
              padding: '4px 10px', borderRadius: 4,
              background: 'rgba(0,0,0,0.2)', border: '1px solid var(--border-light)',
              color: page >= totalPages ? 'var(--text-tertiary)' : 'var(--text-secondary)',
              cursor: page >= totalPages ? 'not-allowed' : 'pointer', fontSize: 11, fontFamily: 'inherit',
            }}
          >
            <i className="fa-solid fa-chevron-right" />
          </button>

          <span style={{ fontSize: 11, color: 'var(--text-tertiary)', marginLeft: 8 }}>
            {page} / {totalPages} 页
          </span>
        </div>
      )}

      {/* 专利详情弹窗 */}
      {selectedPatent && (
        <PatentDetailModal patent={selectedPatent} onClose={() => setSelectedPatent(null)} />
      )}
    </div>
  );
}
