import type { Solution } from '../../types/solution';

const MOCK_SOLUTIONS: Solution[] = [
  {
    id: 'sol_1',
    taskId: 'task_1',
    title: '多层石墨烯-VC 均热板复合散热方案',
    description: '采用三层石墨烯导热膜与 VC 均热板串联结构，石墨烯层负责横向均温，VC 负责纵向热传导，总厚度控制在 0.6mm 以内。',
    principles: ['分割原理', '嵌套原理'],
    confidenceScore: 0.88,
    patentReferences: ['CN115672345A', 'CN115432189A'],
    rating: 4,
  },
  {
    id: 'sol_2',
    taskId: 'task_1',
    title: '相变材料+石墨烯混合散热膜',
    description: '在石墨烯基体中嵌入微胶囊相变材料，利用相变潜热吸收芯片峰值功耗产生的瞬时热量，同时石墨烯提供持续导热路径。',
    principles: ['局部质量原理', '预先作用原理'],
    confidenceScore: 0.76,
    patentReferences: ['CN115890123A'],
    rating: 3,
  },
  {
    id: 'sol_3',
    taskId: 'task_1',
    title: '仿生叶脉分形微通道散热结构',
    description: '模仿植物叶脉分形网络设计微通道液冷散热结构，工质在分形通道中自然循环，无需外部泵驱动，实现高效被动散热。',
    principles: ['复制原理', '反向思维原理'],
    confidenceScore: 0.69,
    patentReferences: ['CN115123456A', 'CN115789012A'],
    rating: 3,
  },
];

function ScoreBar({ label, value, max = 5 }: { label: string; value: number; max?: number }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
      <span style={{ fontSize: 11, color: 'var(--text-tertiary)', width: 60, flexShrink: 0 }}>{label}</span>
      <div style={{ flex: 1, height: 6, borderRadius: 3, background: 'rgba(255,255,255,0.08)', overflow: 'hidden' }}>
        <div style={{ width: `${(value / max) * 100}%`, height: '100%', borderRadius: 3, background: value >= 4 ? 'var(--accent-green)' : value >= 3 ? 'var(--accent-blue)' : '#fbbf24' }} />
      </div>
      <span style={{ fontSize: 11, color: 'var(--text-primary)', fontWeight: 500, width: 24, textAlign: 'right' }}>{value}/{max}</span>
    </div>
  );
}

export default function SolutionMockPage() {
  return (
    <div className="card" style={{ display: 'flex', flexDirection: 'column', gap: 16, width: '100%' }}>
      <div className="card-title">方案生成</div>
      <div style={{ fontSize: 12, color: 'var(--text-secondary)' }}>当前任务的创新方案</div>

      {MOCK_SOLUTIONS.map((sol, idx) => (
        <div
          key={sol.id}
          style={{
            padding: '14px 16px',
            borderRadius: 8,
            background: 'rgba(0,0,0,0.2)',
            border: '1px solid var(--border)',
          }}
        >
          {/* 标题行 */}
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <span
                style={{
                  width: 22,
                  height: 22,
                  borderRadius: '50%',
                  background: 'var(--accent)',
                  color: '#fff',
                  fontSize: 11,
                  fontWeight: 700,
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  flexShrink: 0,
                }}
              >
                {idx + 1}
              </span>
              <span style={{ fontSize: 14, fontWeight: 600, color: 'var(--text-primary)' }}>{sol.title}</span>
            </div>
            <span style={{ fontSize: 13, fontWeight: 600, color: 'var(--accent-green)' }}>
              {Math.round(sol.confidenceScore * 100)}%
            </span>
          </div>

          {/* 描述 */}
          <div style={{ fontSize: 12, color: 'var(--text-secondary)', lineHeight: 1.6, marginBottom: 10 }}>{sol.description}</div>

          {/* 评分 */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: 4, marginBottom: 10 }}>
            <ScoreBar label="综合评分" value={sol.rating} />
          </div>

          {/* 原理 & 专利 */}
          <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap' }}>
            <div>
              <span style={{ fontSize: 10, color: 'var(--text-tertiary)', marginRight: 6 }}>创新原理</span>
              {sol.principles.map((p, i) => (
                <span key={i} style={{ fontSize: 10, padding: '2px 6px', borderRadius: 3, background: 'rgba(59,130,246,0.1)', color: 'var(--accent-blue)', marginRight: 4 }}>{p}</span>
              ))}
            </div>
            <div>
              <span style={{ fontSize: 10, color: 'var(--text-tertiary)', marginRight: 6 }}>参考专利</span>
              {sol.patentReferences.map((p, i) => (
                <span key={i} style={{ fontSize: 10, padding: '2px 6px', borderRadius: 3, background: 'rgba(139,92,246,0.1)', color: 'var(--accent-purple)', marginRight: 4 }}>{p}</span>
              ))}
            </div>
          </div>
        </div>
      ))}
    </div>
  );
}
