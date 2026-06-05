import { usePatentStore } from '../../store/usePatentStore';
import { useTaskStore } from '../../store/useTaskStore';

export function PatentStatsPanel() {
  const stats = usePatentStore((s) => s.stats);
  const loading = usePatentStore((s) => s.loading);
  const selectedTaskId = useTaskStore((s) => s.selectedTaskId);

  return (
    <div className="card" style={{ minHeight: 180 }}>
      <div className="card-title">
        <i className="fa-solid fa-magnifying-glass" style={{ fontSize: 12, color: 'var(--accent-blue)' }} />
        专利检索与分析
      </div>

      {!selectedTaskId ? (
        <div style={{ padding: '30px 0', textAlign: 'center', fontSize: 13, color: 'var(--text-secondary)' }}>
          选择任务查看专利分析
        </div>
      ) : loading ? (
        <div style={{ padding: '30px 0', textAlign: 'center', fontSize: 13, color: 'var(--text-secondary)' }}>
          加载中...
        </div>
      ) : stats ? (
        <>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 10, marginBottom: 14 }}>
            {[
              { label: '检索到相关专利', value: stats.relatedCount.toLocaleString(), unit: '篇', color: 'var(--accent-blue)', change: '↑ 86%', sub: '较通用检索' },
              { label: '高相关专利', value: stats.coreCount.toLocaleString(), unit: '篇', color: 'var(--accent-cyan)', change: '↑ 72%', sub: '较通用检索' },
              { label: '核心专利分析完成', value: stats.analyzedCount.toLocaleString(), unit: '篇', color: 'var(--accent-purple)', change: '↑ 65%', sub: '较通用分析' },
            ].map((item) => (
              <div key={item.label} style={{
                background: 'rgba(0,0,0,0.2)', borderRadius: 8, padding: '10px 12px',
                border: '1px solid var(--border)',
              }}>
                <div style={{ fontSize: 10, color: 'var(--text-tertiary)', marginBottom: 6 }}>{item.label}</div>
                <div style={{ display: 'flex', alignItems: 'baseline', gap: 4 }}>
                  <span style={{ fontSize: 22, fontWeight: 700, color: item.color }}>{item.value}</span>
                  <span style={{ fontSize: 11, color: 'var(--text-tertiary)' }}>{item.unit}</span>
                </div>
                <div style={{ fontSize: 10, color: 'var(--accent-green)', marginTop: 4 }}>
                  {item.sub} <span style={{ fontWeight: 600 }}>{item.change}</span>
                </div>
              </div>
            ))}
          </div>

          {stats.topPatents.length > 0 && (
            <div>
              {stats.topPatents.slice(0, 3).map((p, i) => (
                <div key={p.id} style={{
                  display: 'flex', alignItems: 'center', gap: 10, padding: '8px 0',
                  borderBottom: i < Math.min(stats.topPatents.length, 3) - 1 ? '1px solid var(--border-light)' : 'none',
                  fontSize: 11,
                }}>
                  <span style={{
                    width: 20, height: 20, borderRadius: '50%',
                    background: 'rgba(59,130,246,0.15)', color: 'var(--accent-blue)',
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                    fontSize: 10, fontWeight: 600, flexShrink: 0,
                  }}>
                    {i + 1}
                  </span>
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ color: 'var(--text-primary)', fontWeight: 500, marginBottom: 2, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                      {p.title}
                    </div>
                    <div style={{ color: 'var(--text-tertiary)', fontSize: 10 }}>
                      申请号：{p.patentNumber} · 申请日：{p.filingDate?.slice(0, 10)}
                    </div>
                  </div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 6, flexShrink: 0 }}>
                    <span style={{ fontSize: 11, color: 'var(--accent-green)', fontWeight: 600 }}>
                      相关度 {p.relevanceScore}%
                    </span>
                    <div style={{ display: 'flex', gap: 3 }}>
                      {(p.ipcCodes || []).slice(0, 2).map((code) => (
                        <span key={code} style={{
                          fontSize: 9, padding: '2px 6px', borderRadius: 4,
                          background: 'rgba(59,130,246,0.1)', color: 'var(--accent-blue)',
                          border: '1px solid rgba(59,130,246,0.2)',
                        }}>
                          {code}
                        </span>
                      ))}
                    </div>
                  </div>
                </div>
              ))}
              <div style={{ textAlign: 'center', marginTop: 8 }}>
                <button style={{
                  background: 'none', border: 'none', color: 'var(--accent-blue)',
                  fontSize: 11, cursor: 'pointer', fontFamily: 'inherit',
                }}>
                  查看更多专利 <i className="fa-solid fa-chevron-right" style={{ fontSize: 9 }} />
                </button>
              </div>
            </div>
          )}
        </>
      ) : (
        <div style={{ padding: '30px 0', textAlign: 'center', fontSize: 13, color: 'var(--text-secondary)' }}>
          暂无专利数据
        </div>
      )}
    </div>
  );
}
