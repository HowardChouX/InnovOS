import { useSolutionStore } from '../../store/useSolutionStore';
import { useTaskStore } from '../../store/useTaskStore';

function StarRating({ rating, max = 5 }: { rating: number; max?: number }) {
  return (
    <div style={{ display: 'flex', gap: 2 }}>
      {Array.from({ length: max }, (_, i) => (
        <span key={i} style={{
          fontSize: 14, color: i < rating ? '#fbbf24' : 'rgba(255,255,255,0.15)',
        }}>
          {i < rating ? '★' : '☆'}
        </span>
      ))}
    </div>
  );
}

export function SolutionGeneration() {
  const solutions = useSolutionStore((s) => s.solutions);
  const selectedTaskId = useTaskStore((s) => s.selectedTaskId);
  const loading = useSolutionStore((s) => s.loading);

  const emptyPanel = (msg: string) => (
    <div className="card" style={{ display: 'flex', flexDirection: 'column', width: '100%', minHeight: 200 }}>
      <div className="card-title">
        <i className="fa-solid fa-wand-magic-sparkles" style={{ fontSize: 12, color: 'var(--accent-purple)' }} />
        创新方案生成
      </div>
      <div style={{ padding: '30px 0', textAlign: 'center', fontSize: 13, color: 'var(--text-secondary)' }}>{msg}</div>
    </div>
  );

  if (!selectedTaskId) return emptyPanel('选择一个任务查看创新方案');
  if (loading && solutions.length === 0) return emptyPanel('加载中...');
  if (solutions.length === 0) return emptyPanel('暂无方案数据');

  return (
    <div className="card" style={{ display: 'flex', flexDirection: 'column', width: '100%', minHeight: 300 }}>
      <div className="card-title">
        <i className="fa-solid fa-wand-magic-sparkles" style={{ fontSize: 12, color: 'var(--accent-purple)' }} />
        创新方案生成
      </div>

      <div style={{ flex: 1, overflow: 'auto' }}>
        {/* 推荐创新方向 */}
        <div style={{
          background: 'rgba(0,0,0,0.2)', borderRadius: 8, padding: 12, marginBottom: 12,
          border: '1px solid var(--border)',
        }}>
          <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-primary)', marginBottom: 10 }}>
            推荐创新方向
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
            {solutions.slice(0, 3).map((sol, i) => (
              <div key={sol.id} style={{
                display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                padding: '8px 10px', borderRadius: 6,
                background: 'rgba(59,130,246,0.08)', border: '1px solid rgba(59,130,246,0.15)',
              }}>
                <div>
                  <span style={{ fontSize: 11, color: 'var(--accent-blue)', fontWeight: 600 }}>
                    方向{i + 1}：
                  </span>
                  <span style={{ fontSize: 12, color: 'var(--text-primary)' }}>{sol.title}</span>
                </div>
                <StarRating rating={Math.round(sol.confidenceScore / 20)} />
              </div>
            ))}
          </div>
        </div>

        {/* 方案概述 */}
        <div style={{
          background: 'rgba(0,0,0,0.2)', borderRadius: 8, padding: 12,
          border: '1px solid var(--border)',
        }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 8 }}>
            <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-primary)', display: 'flex', alignItems: 'center', gap: 6 }}>
              <i className="fa-regular fa-lightbulb" style={{ color: 'var(--accent-yellow)' }} />
              方案概述
            </div>
            <i className="fa-solid fa-chevron-right" style={{ fontSize: 10, color: 'var(--text-tertiary)', cursor: 'pointer' }} />
          </div>
          <div style={{ fontSize: 11, color: 'var(--text-secondary)', lineHeight: 1.6 }}>
            {solutions[0]?.description?.slice(0, 120) || '通过固态电解质替换液态电解质，结合界面改性技术和多层结构设计，在提升能量密度的同时有效抑制热失控，提高安全性并延长循环寿命。'}
            {(solutions[0]?.description?.length || 0) > 120 ? '...' : ''}
          </div>
        </div>

        {/* View full solution button */}
        <button style={{
          width: '100%', marginTop: 12, padding: '10px 0',
          background: 'rgba(59,130,246,0.15)', border: '1px solid rgba(59,130,246,0.3)',
          borderRadius: 8, color: 'var(--accent-blue)', fontSize: 13, fontWeight: 500,
          cursor: 'pointer', fontFamily: 'inherit',
        }}>
          查看完整方案 <i className="fa-solid fa-arrow-right" style={{ fontSize: 11, marginLeft: 4 }} />
        </button>
      </div>
    </div>
  );
}
