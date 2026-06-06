import { useMonitorStore } from '../../store/useMonitorStore';

interface CardProps {
  label: string;
  value: string | number;
  color: string;
  icon: string;
}

function StatCard({ label, value, color, icon }: CardProps) {
  return (
    <div style={{
      flex: 1, minWidth: 140, padding: '14px 16px', borderRadius: 10,
      background: 'rgba(0,0,0,0.2)', border: '1px solid var(--border)',
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 8 }}>
        <i className={`fa-solid ${icon}`} style={{ fontSize: 12, color }} />
        <span style={{ fontSize: 12, color: 'var(--text-secondary)' }}>{label}</span>
      </div>
      <div style={{ fontSize: 24, fontWeight: 700, color }}>
        {value}
      </div>
    </div>
  );
}

export function OverviewCards() {
  const overview = useMonitorStore((s) => s.overview);
  const loading = useMonitorStore((s) => s.loading);

  if (loading || !overview) {
    return (
      <div style={{ display: 'flex', gap: 12 }}>
        {[1, 2, 3, 4].map((i) => (
          <div key={i} style={{
            flex: 1, minWidth: 140, height: 80, borderRadius: 10,
            background: 'rgba(0,0,0,0.2)', border: '1px solid var(--border)',
            animation: 'pulse 1.5s infinite',
          }} />
        ))}
      </div>
    );
  }

  return (
    <div style={{ display: 'flex', gap: 12 }}>
      <StatCard
        label="总任务数"
        value={overview.totalTasks}
        color="var(--accent-blue)"
        icon="fa-list-check"
      />
      <StatCard
        label="完成率"
        value={`${overview.successRate}%`}
        color="var(--accent-green)"
        icon="fa-circle-check"
      />
      <StatCard
        label="AI 分析"
        value={overview.totalAnalyses}
        color="var(--accent-purple)"
        icon="fa-brain"
      />
      <StatCard
        label="平均评分"
        value={overview.avgRating > 0 ? `${overview.avgRating}★` : '-'}
        color="var(--accent-yellow)"
        icon="fa-star"
      />
    </div>
  );
}
