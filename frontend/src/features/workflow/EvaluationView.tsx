interface EvaluationScore {
  innovation: number;
  feasibility: number;
  completeness: number;
  conversion: number;
}

interface EvaluationItem {
  solution_title: string;
  evaluation: {
    scores: EvaluationScore;
    overall: number;
    strengths: string[];
    weaknesses: string[];
    recommendations: string[];
  };
}

const SCORE_LABELS: Record<keyof EvaluationScore, string> = {
  innovation: '创新性',
  feasibility: '可行性',
  completeness: '完整性',
  conversion: '转化潜力',
};

const SCORE_COLORS: Record<keyof EvaluationScore, string> = {
  innovation: 'var(--accent-purple)',
  feasibility: 'var(--accent-green)',
  completeness: 'var(--accent-blue)',
  conversion: 'var(--accent-yellow)',
};

function ScoreCard({ label, value, color }: { label: string; value: number; color: string }) {
  return (
    <div style={{
      background: 'rgba(0,0,0,0.2)', borderRadius: 8, padding: 10,
      border: '1px solid var(--border-light)', textAlign: 'center',
    }}>
      <div style={{ fontSize: 10, color: 'var(--text-tertiary)', marginBottom: 4 }}>{label}</div>
      <div style={{ fontSize: 18, fontWeight: 700, color, marginBottom: 6 }}>{value}</div>
      <div style={{ width: '100%', height: 4, borderRadius: 2, background: 'rgba(0,0,0,0.3)', overflow: 'hidden' }}>
        <div style={{ width: `${value}%`, height: '100%', background: color, borderRadius: 2 }} />
      </div>
    </div>
  );
}

function OverallBadge({ overall }: { overall: number }) {
  const color = overall >= 80 ? 'var(--accent-green)' : overall >= 60 ? 'var(--accent-yellow)' : 'var(--accent-red)';
  const label = overall >= 80 ? '优秀' : overall >= 60 ? '良好' : '待改进';
  return (
    <div style={{
      display: 'inline-flex', alignItems: 'center', gap: 6,
      padding: '4px 12px', borderRadius: 6,
      background: `color-mix(in srgb, ${color} 15%, transparent)`,
      border: `1px solid color-mix(in srgb, ${color} 30%, transparent)`,
    }}>
      <span style={{ fontSize: 13, fontWeight: 700, color }}>{overall}</span>
      <span style={{ fontSize: 11, color }}>{label}</span>
    </div>
  );
}

export function EvaluationView({ output }: { output: EvaluationItem[] | null }) {
  if (!output || !Array.isArray(output) || output.length === 0) {
    return (
      <div className="card" style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', minHeight: 200 }}>
        <span style={{ fontSize: 13, color: 'var(--text-tertiary)' }}>暂无评估数据</span>
      </div>
    );
  }

  return (
    <div className="card" style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
      <div className="card-title">
        <i className="fa-solid fa-chart-line" style={{ marginRight: 8, color: 'var(--accent-yellow)' }} />
        方案评估
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
        {output.map((item, i) => {
          const { scores, overall, strengths, weaknesses, recommendations } = item.evaluation;
          const keys = Object.keys(scores) as (keyof EvaluationScore)[];

          return (
            <div key={i} style={{
              background: 'rgba(0,0,0,0.2)', borderRadius: 8, padding: 14,
              border: '1px solid var(--border-light)',
            }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
                <div style={{ fontSize: 14, fontWeight: 600, color: 'var(--text-primary)' }}>{item.solution_title}</div>
                <OverallBadge overall={overall} />
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 8, marginBottom: 12 }}>
                {keys.map((key) => (
                  <ScoreCard key={key} label={SCORE_LABELS[key]} value={scores[key]} color={SCORE_COLORS[key]} />
                ))}
              </div>

              <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap' }}>
                {strengths.length > 0 && (
                  <div style={{ flex: 1, minWidth: 160 }}>
                    <div style={{ fontSize: 11, fontWeight: 600, color: 'var(--accent-green)', marginBottom: 4 }}>优势</div>
                    <ul style={{ margin: 0, paddingLeft: 16, fontSize: 11, color: 'var(--text-secondary)', lineHeight: 1.8 }}>
                      {strengths.map((s, j) => <li key={j}>{s}</li>)}
                    </ul>
                  </div>
                )}
                {weaknesses.length > 0 && (
                  <div style={{ flex: 1, minWidth: 160 }}>
                    <div style={{ fontSize: 11, fontWeight: 600, color: 'var(--accent-red)', marginBottom: 4 }}>不足</div>
                    <ul style={{ margin: 0, paddingLeft: 16, fontSize: 11, color: 'var(--text-secondary)', lineHeight: 1.8 }}>
                      {weaknesses.map((w, j) => <li key={j}>{w}</li>)}
                    </ul>
                  </div>
                )}
              </div>

              {recommendations.length > 0 && (
                <div style={{ marginTop: 8, padding: 8, borderRadius: 6, background: 'rgba(59,130,246,0.08)', border: '1px solid rgba(59,130,246,0.15)' }}>
                  <div style={{ fontSize: 11, fontWeight: 600, color: 'var(--accent-blue)', marginBottom: 4 }}>建议</div>
                  <div style={{ fontSize: 11, color: 'var(--text-secondary)', lineHeight: 1.6 }}>
                    {recommendations.map((r, j) => <div key={j}>• {r}</div>)}
                  </div>
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
