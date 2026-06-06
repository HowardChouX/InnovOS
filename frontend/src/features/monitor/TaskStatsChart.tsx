import { useMonitorStore } from '../../store/useMonitorStore';
import { GlassPanel } from '../../components/ui/GlassPanel';

const STATUS_COLORS: Record<string, string> = {
  pending: 'var(--accent-yellow)',
  analyzing: 'var(--accent-blue)',
  completed: 'var(--accent-green)',
  failed: 'var(--accent-red)',
};

const STATUS_LABELS: Record<string, string> = {
  pending: '待处理',
  analyzing: '分析中',
  completed: '已完成',
  failed: '失败',
};

export function TaskStatsChart() {
  const taskStats = useMonitorStore((s) => s.taskStats);

  if (!taskStats) return null;

  const { byStatus, recent7days } = taskStats;
  const total = Object.values(byStatus).reduce((a, b) => a + b, 0);
  const maxCount = Math.max(...recent7days.map((d) => d.count), 1);

  return (
    <div style={{ display: 'flex', gap: 12 }}>
      {/* 任务状态分布 */}
      <GlassPanel style={{ flex: 1 }}>
        <div className="card-title">
          任务状态分布
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          {Object.entries(byStatus).map(([status, count]) => {
            const pct = total > 0 ? ((count as number) / total * 100).toFixed(1) : 0;
            return (
              <div key={status} style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <div style={{
                  width: 8, height: 8, borderRadius: '50%',
                  background: STATUS_COLORS[status] || 'var(--text-tertiary)',
                }} />
                <span style={{ fontSize: 12, color: 'var(--text-secondary)', width: 50 }}>
                  {STATUS_LABELS[status] || status}
                </span>
                <div style={{
                  flex: 1, height: 6, borderRadius: 3,
                  background: 'rgba(255,255,255,0.05)',
                }}>
                  <div style={{
                    width: `${pct}%`, height: '100%', borderRadius: 3,
                    background: STATUS_COLORS[status] || 'var(--text-tertiary)',
                    transition: 'width 0.3s',
                  }} />
                </div>
                <span style={{ fontSize: 11, color: 'var(--text-tertiary)', width: 40, textAlign: 'right' }}>
                  {count as number} ({pct}%)
                </span>
              </div>
            );
          })}
        </div>
      </GlassPanel>

      {/* 近7天趋势 */}
      <GlassPanel style={{ flex: 1 }}>
        <div className="card-title">
          近7天任务趋势
        </div>
        <div style={{
          display: 'flex', alignItems: 'flex-end', gap: 4,
          height: 100, paddingTop: 10,
        }}>
          {recent7days.length === 0 ? (
            <div style={{
              flex: 1, textAlign: 'center', fontSize: 12,
              color: 'var(--text-tertiary)', paddingTop: 30,
            }}>
              暂无数据
            </div>
          ) : (
            recent7days.map((d) => (
              <div key={d.date} style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 4 }}>
                <span style={{ fontSize: 9, color: 'var(--text-tertiary)' }}>{d.count}</span>
                <div style={{
                  width: '100%', maxWidth: 30,
                  height: `${(d.count / maxCount) * 80}px`,
                  minHeight: 4,
                  borderRadius: 3,
                  background: 'linear-gradient(180deg, var(--accent-cyan), var(--accent-blue))',
                  transition: 'height 0.3s',
                }} />
                <span style={{ fontSize: 8, color: 'var(--text-tertiary)' }}>
                  {d.date.slice(5)}
                </span>
              </div>
            ))
          )}
        </div>
      </GlassPanel>
    </div>
  );
}
