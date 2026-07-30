import type { ProblemModeling } from '../../types/modeling';

const MOCK_MODELING: ProblemModeling = {
  id: 'model_1',
  taskId: 'task_1',
  problemElements: {
    coreGoal: '提升手机散热效率，降低核心温度 10°C',
    techObject: '石墨烯复合散热结构',
    constraints: ['功耗不超过 5W', '厚度 ≤ 0.8mm', '符合 RoHS 标准'],
    potentialConflicts: [
      { id: 'c1', label: '散热效率 vs 轻薄设计', description: '增加散热面积与机身厚度之间的矛盾' },
      { id: 'c2', label: '成本 vs 性能', description: '石墨烯材料成本与导热系数的权衡' },
    ],
  },
  conflicts: [
    {
      type: '物理矛盾',
      description: '散热结构需要增大面积以提高散热效率，但同时需要保持轻薄以满足便携性需求',
      parameters: [
        { name: '散热面积', direction: '增大', requirement: '提高热传导效率' },
        { name: '结构厚度', direction: '减小', requirement: '满足轻薄设计' },
      ],
      severity: '高',
    },
  ],
  recommendedPrinciples: ['分割原理', '局部质量原理', '嵌套原理'],
  innovationDirections: [
    { direction: '多层石墨烯复合结构', description: '采用分层设计实现散热与轻薄的平衡', confidence: 0.85 },
    { direction: '相变材料辅助散热', description: '在热点区域嵌入相变材料吸收瞬时热量', confidence: 0.72 },
  ],
  modelStructure: {
    problemType: '物理矛盾',
    complexity: '中等',
    keyFactors: ['导热系数', '结构厚度', '材料成本', '制造工艺'],
    rootCause: '散热需求与轻薄设计的根本冲突',
    solutionSpace: '通过材料创新和结构优化实现突破',
  },
};

export default function ProblemDefinitionMockPage() {
  const m = MOCK_MODELING;

  return (
    <div className="card" style={{ display: 'flex', flexDirection: 'column', gap: 16, width: '100%' }}>
      <div className="card-title">问题定义</div>
      <div style={{ fontSize: 12, color: 'var(--text-secondary)' }}>当前任务的问题建模结果</div>

      {/* 核心目标 */}
      <div style={{ padding: '10px 14px', borderRadius: 8, background: 'rgba(0,0,0,0.2)', border: '1px solid var(--border)' }}>
        <div style={{ fontSize: 11, color: 'var(--text-tertiary)', marginBottom: 4 }}>核心目标</div>
        <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-primary)' }}>{m.problemElements.coreGoal}</div>
        <div style={{ fontSize: 11, color: 'var(--text-secondary)', marginTop: 4 }}>技术对象：{m.problemElements.techObject}</div>
      </div>

      {/* 约束条件 */}
      <div style={{ padding: '10px 14px', borderRadius: 8, background: 'rgba(0,0,0,0.2)', border: '1px solid var(--border)' }}>
        <div style={{ fontSize: 11, color: 'var(--text-tertiary)', marginBottom: 6 }}>约束条件</div>
        <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
          {m.problemElements.constraints.map((c, i) => (
            <span key={i} style={{ fontSize: 11, padding: '3px 8px', borderRadius: 4, background: 'rgba(251,191,36,0.1)', color: '#fbbf24', border: '1px solid rgba(251,191,36,0.2)' }}>{c}</span>
          ))}
        </div>
      </div>

      {/* 冲突 */}
      <div style={{ padding: '10px 14px', borderRadius: 8, background: 'rgba(239,68,68,0.06)', border: '1px solid rgba(239,68,68,0.2)' }}>
        <div style={{ fontSize: 11, color: 'var(--text-tertiary)', marginBottom: 6 }}>核心冲突</div>
        {m.conflicts.map((conflict, i) => (
          <div key={i}>
            <div style={{ fontSize: 12, fontWeight: 600, color: '#ef4444', marginBottom: 4 }}>{conflict.type} — 严重度: {conflict.severity}</div>
            <div style={{ fontSize: 12, color: 'var(--text-secondary)', marginBottom: 6 }}>{conflict.description}</div>
            <div style={{ display: 'flex', gap: 8 }}>
              {conflict.parameters.map((p, j) => (
                <span key={j} style={{ fontSize: 10, padding: '2px 8px', borderRadius: 4, background: 'rgba(239,68,68,0.1)', color: '#f87171' }}>
                  {p.name}: {p.direction}（{p.requirement}）
                </span>
              ))}
            </div>
          </div>
        ))}
      </div>

      {/* 创新方向 */}
      <div style={{ padding: '10px 14px', borderRadius: 8, background: 'rgba(34,197,94,0.06)', border: '1px solid rgba(34,197,94,0.2)' }}>
        <div style={{ fontSize: 11, color: 'var(--text-tertiary)', marginBottom: 6 }}>创新方向</div>
        {m.innovationDirections.map((d, i) => (
          <div key={i} style={{ marginBottom: i < m.innovationDirections.length - 1 ? 8 : 0 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <span style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-primary)' }}>{d.direction}</span>
              <span style={{ fontSize: 11, fontWeight: 600, color: 'var(--accent-green)' }}>{Math.round(d.confidence * 100)}%</span>
            </div>
            <div style={{ fontSize: 11, color: 'var(--text-secondary)', marginTop: 2 }}>{d.description}</div>
          </div>
        ))}
      </div>

      {/* 模型结构 */}
      <div style={{ padding: '10px 14px', borderRadius: 8, background: 'rgba(0,0,0,0.2)', border: '1px solid var(--border)' }}>
        <div style={{ fontSize: 11, color: 'var(--text-tertiary)', marginBottom: 6 }}>模型结构</div>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
          <div><span style={{ fontSize: 10, color: 'var(--text-tertiary)' }}>问题类型：</span><span style={{ fontSize: 12, color: 'var(--text-primary)' }}>{m.modelStructure.problemType}</span></div>
          <div><span style={{ fontSize: 10, color: 'var(--text-tertiary)' }}>复杂度：</span><span style={{ fontSize: 12, color: 'var(--text-primary)' }}>{m.modelStructure.complexity}</span></div>
          <div style={{ gridColumn: '1 / -1' }}><span style={{ fontSize: 10, color: 'var(--text-tertiary)' }}>根本原因：</span><span style={{ fontSize: 12, color: 'var(--text-primary)' }}>{m.modelStructure.rootCause}</span></div>
          <div style={{ gridColumn: '1 / -1' }}><span style={{ fontSize: 10, color: 'var(--text-tertiary)' }}>解空间：</span><span style={{ fontSize: 12, color: 'var(--text-primary)' }}>{m.modelStructure.solutionSpace}</span></div>
        </div>
      </div>
    </div>
  );
}
