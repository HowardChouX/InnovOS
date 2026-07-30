import type { Evaluation } from '../../types/evaluation';

const MOCK_EVALUATIONS: Evaluation[] = [
  {
    id: 'eval_1',
    solutionId: 'sol_1',
    dimension: '创新性评估',
    score: 87,
    details: {},
    status: 'completed',
    createdAt: '2026-07-04T10:00:00Z',
    rootCauseCut: true,
    originalContradictionResolved: true,
    newContradictions: [],
    functionDeficitsFilled: ['散热效率提升', '厚度控制'],
    newHarmfulInteractions: [],
    ifrDistance: '接近理想解',
    ifrGapDescription: '散热结构自身不增加额外重量和厚度',
    ifrParametersAchieved: ['导热系数 ≥ 1500 W/mK', '厚度 ≤ 0.6mm'],
    overallVerdict: '优秀',
    evolutionAlignment: 0.9,
    alignedLaws: ['向超系统进化', '动态化法则'],
    misalignedLaws: [],
    maturity: '成长期',
    confidence: 0.88,
  },
  {
    id: 'eval_2',
    solutionId: 'sol_1',
    dimension: '可行性评估',
    score: 82,
    details: {},
    status: 'completed',
    createdAt: '2026-07-04T10:01:00Z',
    rootCauseCut: true,
    originalContradictionResolved: true,
    newContradictions: ['成本较高'],
    functionDeficitsFilled: ['量产工艺可行性'],
    newHarmfulInteractions: ['石墨烯层间剥离风险'],
    ifrDistance: '较近',
    ifrGapDescription: '材料成本需进一步优化',
    ifrParametersAchieved: ['量产良率 ≥ 90%'],
    overallVerdict: '良好',
    evolutionAlignment: 0.75,
    alignedLaws: ['子系统不均衡进化'],
    misalignedLaws: ['提高理想度法则'],
    maturity: '成长期',
    confidence: 0.82,
  },
  {
    id: 'eval_3',
    solutionId: 'sol_2',
    dimension: '创新性评估',
    score: 74,
    details: {},
    status: 'completed',
    createdAt: '2026-07-04T10:02:00Z',
    rootCauseCut: true,
    originalContradictionResolved: false,
    newContradictions: ['相变材料循环寿命'],
    functionDeficitsFilled: ['瞬时散热能力'],
    newHarmfulInteractions: ['微胶囊破裂风险'],
    ifrDistance: '中等',
    ifrGapDescription: '相变材料的长期稳定性待验证',
    ifrParametersAchieved: ['潜热密度 ≥ 150 J/g'],
    overallVerdict: '良好',
    evolutionAlignment: 0.65,
    alignedLaws: ['向微观级进化'],
    misalignedLaws: ['协调性法则'],
    maturity: '婴儿期',
    confidence: 0.76,
  },
];

function DimensionCard({ label, score }: { label: string; score: number }) {
  const color = score >= 80 ? 'var(--accent-green)' : score >= 60 ? '#fbbf24' : '#ef4444';
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
      <span style={{ fontSize: 11, color: 'var(--text-tertiary)', width: 80, flexShrink: 0 }}>{label}</span>
      <div style={{ flex: 1, height: 6, borderRadius: 3, background: 'rgba(255,255,255,0.08)', overflow: 'hidden' }}>
        <div style={{ width: `${score}%`, height: '100%', borderRadius: 3, background: color }} />
      </div>
      <span style={{ fontSize: 12, fontWeight: 600, color, width: 36, textAlign: 'right' }}>{score}</span>
    </div>
  );
}

export default function EvaluationMockPage() {
  return (
    <div className="card" style={{ display: 'flex', flexDirection: 'column', gap: 16, width: '100%' }}>
      <div className="card-title">方案评估</div>
      <div style={{ fontSize: 12, color: 'var(--text-secondary)' }}>当前任务的四维评估结果</div>

      {MOCK_EVALUATIONS.map((ev) => (
        <div
          key={ev.id}
          style={{
            padding: '14px 16px',
            borderRadius: 8,
            background: 'rgba(0,0,0,0.2)',
            border: '1px solid var(--border)',
          }}
        >
          {/* 标题 */}
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10 }}>
            <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-primary)' }}>
              {ev.dimension}
              <span style={{ fontSize: 10, color: 'var(--text-tertiary)', fontWeight: 400, marginLeft: 8 }}>
                方案 {ev.solutionId}
              </span>
            </div>
            <span
              style={{
                fontSize: 10,
                padding: '2px 8px',
                borderRadius: 4,
                background: ev.overallVerdict === '优秀' ? 'rgba(34,197,94,0.1)' : 'rgba(59,130,246,0.1)',
                color: ev.overallVerdict === '优秀' ? 'var(--accent-green)' : 'var(--accent-blue)',
              }}
            >
              {ev.overallVerdict}
            </span>
          </div>

          {/* 分数条 */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: 4, marginBottom: 10 }}>
            <DimensionCard label="综合评分" score={ev.score} />
          </div>

          {/* 关键指标 */}
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 6, fontSize: 11, marginBottom: 8 }}>
            <div style={{ color: 'var(--text-tertiary)' }}>
              根因切断：
              <span style={{ color: ev.rootCauseCut ? 'var(--accent-green)' : '#ef4444' }}>
                {ev.rootCauseCut ? '是' : '否'}
              </span>
            </div>
            <div style={{ color: 'var(--text-tertiary)' }}>
              原矛盾解决：
              <span style={{ color: ev.originalContradictionResolved ? 'var(--accent-green)' : '#ef4444' }}>
                {ev.originalContradictionResolved ? '是' : '否'}
              </span>
            </div>
            <div style={{ color: 'var(--text-tertiary)' }}>
              进化对齐度：
              <span style={{ color: 'var(--text-primary)', fontWeight: 500 }}>
                {Math.round(ev.evolutionAlignment * 100)}%
              </span>
            </div>
            <div style={{ color: 'var(--text-tertiary)' }}>
              技术成熟度：
              <span style={{ color: 'var(--text-primary)', fontWeight: 500 }}>{ev.maturity}</span>
            </div>
          </div>

          {/* IFR */}
          <div style={{ fontSize: 11, marginBottom: 6 }}>
            <span style={{ color: 'var(--text-tertiary)' }}>理想最终解（IFR）：</span>
            <span style={{ color: 'var(--text-secondary)' }}>{ev.ifrGapDescription}</span>
          </div>

          {/* 新矛盾 */}
          {ev.newContradictions.length > 0 && (
            <div style={{ fontSize: 11, marginBottom: 4 }}>
              <span style={{ color: 'var(--text-tertiary)' }}>新矛盾：</span>
              {ev.newContradictions.map((c, i) => (
                <span key={i} style={{ fontSize: 10, padding: '2px 6px', borderRadius: 3, background: 'rgba(239,68,68,0.1)', color: '#f87171', marginLeft: 4 }}>{c}</span>
              ))}
            </div>
          )}

          {/* 对齐法则 */}
          <div style={{ fontSize: 11, display: 'flex', gap: 6, flexWrap: 'wrap', marginTop: 4 }}>
            {ev.alignedLaws.map((law, i) => (
              <span key={i} style={{ padding: '2px 6px', borderRadius: 3, background: 'rgba(34,197,94,0.1)', color: 'var(--accent-green)' }}>{law}</span>
            ))}
            {ev.misalignedLaws.map((law, i) => (
              <span key={i} style={{ padding: '2px 6px', borderRadius: 3, background: 'rgba(239,68,68,0.1)', color: '#f87171' }}>{law}</span>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}
