import { useMemo } from 'react';

interface PatentItem {
  title: string;
  abstract: string;
  relevance: number;
  patentNumber?: string;
}

function RelevanceBadge({ relevance }: { relevance: number }) {
  const { bg, color, label } = useMemo(() => {
    if (relevance >= 80) return { bg: 'rgba(74,222,128,0.15)', color: 'var(--accent-green)', label: '高相关' };
    if (relevance >= 50) return { bg: 'rgba(251,191,36,0.15)', color: 'var(--accent-yellow)', label: '中相关' };
    return { bg: 'rgba(148,163,184,0.15)', color: 'var(--text-tertiary)', label: '低相关' };
  }, [relevance]);

  return (
    <div style={{
      display: 'inline-flex', alignItems: 'center', gap: 4,
      fontSize: 11, fontWeight: 600, padding: '2px 8px', borderRadius: 4, whiteSpace: 'nowrap',
      background: bg, color,
    }}>
      <span>{label}</span>
      <span>{relevance}%</span>
    </div>
  );
}

export function PatentSearchView({ output }: { output: PatentItem[] | null }) {
  if (!output || !Array.isArray(output) || output.length === 0) {
    return (
      <div className="card" style={{
        display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
        minHeight: 200, gap: 12,
      }}>
        <i className="fa-solid fa-file-lines" style={{ fontSize: 32, color: 'var(--text-tertiary)', opacity: 0.3 }} />
        <span style={{ fontSize: 13, color: 'var(--text-tertiary)' }}>暂无专利数据</span>
      </div>
    );
  }

  return (
    <div className="card" style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
      <div className="card-title">
        <i className="fa-solid fa-file-lines" style={{ marginRight: 8, color: 'var(--accent-cyan)' }} />
        专利检索
        <span style={{
          marginLeft: 8, fontSize: 11, padding: '2px 8px', borderRadius: 10,
          background: 'rgba(59,130,246,0.15)', color: 'var(--accent-blue)',
        }}>
          {output.length} 项
        </span>
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
        {output.map((patent, i) => (
          <div key={i} style={{
            background: 'rgba(0,0,0,0.2)', borderRadius: 8, padding: 14,
            border: '1px solid var(--border-light)',
          }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 8 }}>
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{
                  fontSize: 14, fontWeight: 600, color: 'var(--text-primary)',
                  marginBottom: 2, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
                }}>
                  {patent.title}
                </div>
                {patent.patentNumber && (
                  <div style={{ fontSize: 11, color: 'var(--text-tertiary)' }}>
                    <i className="fa-regular fa-file" style={{ marginRight: 4, fontSize: 10 }} />
                    专利号: {patent.patentNumber}
                  </div>
                )}
              </div>
              <RelevanceBadge relevance={patent.relevance} />
            </div>
            <div style={{
              fontSize: 12, color: 'var(--text-secondary)', lineHeight: 1.5,
              display: '-webkit-box', WebkitLineClamp: 3, WebkitBoxOrient: 'vertical', overflow: 'hidden',
            }}>
              {patent.abstract}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
