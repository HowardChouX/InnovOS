import { useMemo } from 'react';

interface SolutionItem {
  title: string;
  description: string;
  principles?: string[];
  confidenceScore?: number;
  patentReferences?: string[];
}

function ConfidenceBar({ score }: { score: number }) {
  const color = useMemo(() => {
    if (score >= 70) return 'var(--accent-green)';
    if (score >= 40) return 'var(--accent-yellow)';
    return 'var(--accent-red)';
  }, [score]);

  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
      <div style={{ width: 60, height: 6, borderRadius: 3, background: 'rgba(0,0,0,0.3)', overflow: 'hidden' }}>
        <div style={{
          width: `${score}%`, height: '100%',
          background: color, borderRadius: 3,
          transition: 'width 0.4s ease',
        }} />
      </div>
      <span style={{ fontSize: 10, color, fontWeight: 600 }}>{score}%</span>
    </div>
  );
}

export function SolutionGenView({ output }: { output: SolutionItem[] | null }) {
  if (!output || !Array.isArray(output) || output.length === 0) {
    return (
      <div className="card" style={{
        display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
        minHeight: 200, gap: 12,
      }}>
        <i className="fa-solid fa-wand-magic-sparkles" style={{ fontSize: 32, color: 'var(--text-tertiary)', opacity: 0.3 }} />
        <span style={{ fontSize: 13, color: 'var(--text-tertiary)' }}>暂无方案数据</span>
      </div>
    );
  }

  return (
    <div className="card" style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
      <div className="card-title">
        <i className="fa-solid fa-wand-magic-sparkles" style={{ marginRight: 8, color: 'var(--accent-green)' }} />
        方案生成
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
        {output.map((sol, i) => (
          <div key={i} style={{
            background: 'rgba(0,0,0,0.2)', borderRadius: 8, padding: 14,
            border: '1px solid var(--border-light)',
          }}>
            <div style={{
              display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start',
              marginBottom: 8, gap: 8,
            }}>
              <div style={{ fontSize: 14, fontWeight: 600, color: 'var(--text-primary)' }}>
                方案 {i + 1}: {sol.title}
              </div>
              {sol.confidenceScore !== undefined && (
                <ConfidenceBar score={sol.confidenceScore} />
              )}
            </div>

            <div style={{
              fontSize: 12, color: 'var(--text-secondary)', lineHeight: 1.5, marginBottom: 8,
              display: '-webkit-box', WebkitLineClamp: 4, WebkitBoxOrient: 'vertical', overflow: 'hidden',
            }}>
              {sol.description}
            </div>

            {sol.principles && sol.principles.length > 0 && (
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4, marginBottom: 8 }}>
                {sol.principles.map((p, j) => (
                  <span key={j} style={{
                    padding: '2px 8px', borderRadius: 3, fontSize: 10,
                    background: 'rgba(251,191,36,0.1)', border: '1px solid rgba(251,191,36,0.2)',
                    color: 'var(--accent-yellow)',
                  }}>
                    <i className="fa-regular fa-lightbulb" style={{ marginRight: 4, fontSize: 9 }} />
                    {p}
                  </span>
                ))}
              </div>
            )}

            {sol.patentReferences && sol.patentReferences.length > 0 && (
              <div style={{ fontSize: 10, color: 'var(--text-tertiary)', display: 'flex', alignItems: 'center', gap: 4 }}>
                <i className="fa-regular fa-copyright" style={{ fontSize: 9 }} />
                参考专利: {sol.patentReferences.join('、')}
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
