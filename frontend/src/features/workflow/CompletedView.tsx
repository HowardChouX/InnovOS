function SummaryItem({ icon, label, value, color }: { icon: string; label: string; value: string; color: string }) {
  return (
    <div style={{
      background: 'rgba(0,0,0,0.2)', borderRadius: 8, padding: '10px 16px',
      border: '1px solid var(--border-light)', display: 'flex', alignItems: 'center', gap: 10,
    }}>
      <i className={icon} style={{ fontSize: 14, color }} />
      <div>
        <div style={{ fontSize: 10, color: 'var(--text-tertiary)', marginBottom: 1 }}>{label}</div>
        <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-primary)' }}>{value}</div>
      </div>
    </div>
  );
}

function parseReport(output: any) {
  if (!output) return null;
  if (typeof output === 'string') {
    try { output = JSON.parse(output); } catch { return null; }
  }
  if (typeof output === 'object' && output.title) return output;
  return null;
}

export function CompletedView({ output }: { output: any }) {
  const report = parseReport(output);

  if (!report) {
    return (
      <div className="card" style={{
        display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
        minHeight: 280, gap: 20, padding: 40,
      }}>
        <div style={{
          width: 64, height: 64, borderRadius: '50%',
          background: 'rgba(74,222,128,0.15)', border: '2px solid rgba(74,222,128,0.3)',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
        }}>
          <i className="fa-solid fa-check" style={{ fontSize: 28, color: 'var(--accent-green)' }} />
        </div>
        <div style={{ textAlign: 'center' }}>
          <h2 style={{ fontSize: 20, fontWeight: 700, color: 'var(--text-primary)', margin: '0 0 8px' }}>分析完成</h2>
          <p style={{ fontSize: 13, color: 'var(--text-secondary)', margin: 0 }}>
            所有分析步骤已完成。
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="card" style={{ display: 'flex', flexDirection: 'column', gap: 16, padding: 20 }}>
      {/* 报告标题 */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
        <i className="fa-solid fa-file-lines" style={{ fontSize: 20, color: 'var(--accent-green)' }} />
        <h2 style={{ fontSize: 18, fontWeight: 700, color: 'var(--text-primary)', margin: 0 }}>
          {report.title}
        </h2>
      </div>

      {/* 执行摘要 */}
      {report.summary && (
        <div style={{
          padding: 14, borderRadius: 8, background: 'rgba(74,222,128,0.08)',
          border: '1px solid rgba(74,222,128,0.2)',
        }}>
          <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--accent-green)', marginBottom: 6 }}>
            <i className="fa-solid fa-lightbulb" style={{ marginRight: 4 }} />
            执行摘要
          </div>
          <p style={{ fontSize: 13, color: 'var(--text-secondary)', margin: 0, lineHeight: 1.7 }}>
            {report.summary}
          </p>
        </div>
      )}

      {/* 报告章节 */}
      {report.sections && report.sections.length > 0 && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          {report.sections.map((section: any, i: number) => (
            <div key={i} style={{
              padding: 14, borderRadius: 8,
              background: 'rgba(0,0,0,0.2)', border: '1px solid var(--border-light)',
            }}>
              <div style={{ fontSize: 14, fontWeight: 600, color: 'var(--text-primary)', marginBottom: 8 }}>
                {section.heading}
              </div>
              <div style={{ fontSize: 13, color: 'var(--text-secondary)', lineHeight: 1.7, whiteSpace: 'pre-wrap' }}>
                {section.content}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* 推荐方案 */}
      {report.topSolutions && report.topSolutions.length > 0 && (
        <div style={{
          padding: 14, borderRadius: 8,
          background: 'rgba(59,130,246,0.08)', border: '1px solid rgba(59,130,246,0.2)',
        }}>
          <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--accent-blue)', marginBottom: 6 }}>
            <i className="fa-solid fa-ranking-star" style={{ marginRight: 4 }} />
            推荐方案
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
            {report.topSolutions.map((sol: string, i: number) => (
              <div key={i} style={{ fontSize: 13, color: 'var(--text-secondary)' }}>
                {i + 1}. {sol}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* 建议 */}
      {report.recommendations && report.recommendations.length > 0 && (
        <div style={{
          padding: 14, borderRadius: 8,
          background: 'rgba(139,92,246,0.08)', border: '1px solid rgba(139,92,246,0.2)',
        }}>
          <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--accent-purple)', marginBottom: 6 }}>
            <i className="fa-solid fa-clipboard-list" style={{ marginRight: 4 }} />
            实施建议
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
            {report.recommendations.map((rec: string, i: number) => (
              <div key={i} style={{ fontSize: 13, color: 'var(--text-secondary)', lineHeight: 1.6 }}>
                - {rec}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
