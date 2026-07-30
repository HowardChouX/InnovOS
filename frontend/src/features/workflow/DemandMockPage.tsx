import { type Demand } from '../workflow/DemandPortraitView';

// Mock 数据：模拟手机散热任务的需求分析
const MOCK_DEMANDS: Demand[] = [
  {
    id: 'demand_1',
    source: '用户反馈',
    category: '性能需求',
    description: '手机高负载运行时 CPU 温度需控制在 45°C 以内，避免降频',
    priority: 0.95,
    user_rating: null,
  },
  {
    id: 'demand_2',
    source: '产品规划',
    category: '体验需求',
    description: '游戏场景下机身表面温度不超过 42°C，手感舒适',
    priority: 0.9,
    user_rating: null,
  },
  {
    id: 'demand_3',
    source: '技术挑战',
    category: '功耗需求',
    description: '散热系统功耗预算 3W 以内，不影响电池续航',
    priority: 0.85,
    user_rating: null,
  },
  {
    id: 'demand_4',
    source: '竞品分析',
    category: '空间需求',
    description: '内部空间受限，散热模组厚度需控制在 0.8mm 以内',
    priority: 0.88,
    user_rating: null,
  },
  {
    id: 'demand_5',
    source: '质量标准',
    category: '可靠性需求',
    description: 'VC 均热板导热效率需达到 95% 以上，均温性 ±1.5°C',
    priority: 0.92,
    user_rating: null,
  },
];

export default function DemandMockPage() {
  return (
    <div className="card" style={{ display: 'flex', flexDirection: 'column', gap: 16, width: '100%' }}>
      <div className="card-title">
        需求分析
      </div>

      <div style={{ fontSize: 12, color: 'var(--text-secondary)', marginBottom: 4 }}>
        当前任务的需求洞察
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
        {MOCK_DEMANDS.map((demand) => (
          <div
            key={demand.id}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 12,
              padding: '10px 14px',
              borderRadius: 8,
              background: 'rgba(0,0,0,0.2)',
              border: '1px solid var(--border)',
            }}
          >
            <div style={{ flex: 1, minWidth: 0 }}>
              <div
                style={{
                  fontSize: 13,
                  fontWeight: 600,
                  color: 'var(--text-primary)',
                  marginBottom: 2,
                }}
              >
                {demand.description}
              </div>
              <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
                <span
                  style={{
                    fontSize: 10,
                    padding: '1px 6px',
                    borderRadius: 3,
                    background: 'rgba(59,130,246,0.1)',
                    color: 'var(--accent-blue)',
                  }}
                >
                  {demand.category}
                </span>
                <span style={{ fontSize: 10, color: 'var(--text-tertiary)' }}>{demand.source}</span>
              </div>
            </div>
            <div style={{ fontSize: 12, color: 'var(--text-tertiary)', fontWeight: 500 }}>
              优先级: {Math.round(demand.priority * 100)}%
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
