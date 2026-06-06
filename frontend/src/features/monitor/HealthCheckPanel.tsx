import { useMonitorStore } from '../../store/useMonitorStore';
import { GlassPanel } from '../../components/ui/GlassPanel';

export function HealthCheckPanel() {
  const health = useMonitorStore((s) => s.health);

  if (!health) return null;

  const statusConfig = {
    healthy: { color: 'var(--accent-green)', label: '健康' },
    degraded: { color: 'var(--accent-yellow)', label: '异常' },
  };

  const checkConfig = {
    ok: { color: 'var(--accent-green)', icon: 'fa-check-circle' },
    warning: { color: 'var(--accent-yellow)', icon: 'fa-exclamation-triangle' },
    error: { color: 'var(--accent-red)', icon: 'fa-times-circle' },
    skipped: { color: 'var(--text-tertiary)', icon: 'fa-minus-circle' },
  };

  const overall = statusConfig[health.status] || statusConfig.degraded;

  const checks = [
    {
      label: '数据库连接',
      icon: 'fa-database',
      ...health.checks.database,
      detail: health.checks.database.responseMs !== undefined
        ? `响应时间 ${health.checks.database.responseMs}ms`
        : health.checks.database.message || '未知',
    },
    {
      label: '磁盘空间',
      icon: 'fa-hard-drive',
      ...health.checks.disk,
      detail: health.checks.disk.freeGB !== undefined
        ? `可用 ${health.checks.disk.freeGB}GB (${health.checks.disk.usedPercent}% 已用)`
        : health.checks.disk.message || '未知',
    },
    {
      label: '内存使用',
      icon: 'fa-memory',
      ...health.checks.memory,
      detail: health.checks.memory.usedPercent !== undefined
        ? `可用 ${health.checks.memory.availableGB}GB (${health.checks.memory.usedPercent}% 已用)`
        : health.checks.memory.message || '未知',
    },
    {
      label: '后端响应',
      icon: 'fa-bolt',
      ...health.checks.backend,
      detail: health.checks.backend.responseMs !== undefined
        ? `响应时间 ${health.checks.backend.responseMs}ms`
        : health.checks.backend.message || '未知',
    },
    {
      label: 'AI 接口',
      icon: 'fa-robot',
      ...health.checks.aiApi,
      detail: health.checks.aiApi.responseMs !== undefined
        ? `${health.checks.aiApi.message} 响应 ${health.checks.aiApi.responseMs}ms`
        : health.checks.aiApi.message || '未知',
    },
  ];

  return (
    <GlassPanel>
      <div className="card-title">
        健康检查
        <span style={{
          marginLeft: 'auto',
          fontSize: 10, padding: '2px 8px', borderRadius: 4,
          background: `${overall.color}20`, color: overall.color,
        }}>
          {overall.label}
        </span>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 10 }}>
        {checks.map((check) => {
          const config = checkConfig[check.status as keyof typeof checkConfig] || checkConfig.ok;
          return (
            <div key={check.label} style={{
              padding: '10px 12px', borderRadius: 6,
              background: 'rgba(0,0,0,0.15)', border: '1px solid var(--border-light)',
            }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 }}>
                <i className={`fa-solid ${check.icon}`} style={{ fontSize: 11, color: 'var(--text-secondary)' }} />
                <span style={{ fontSize: 12, color: 'var(--text-secondary)' }}>{check.label}</span>
                <i className={`fa-solid ${config.icon}`} style={{ fontSize: 10, color: config.color, marginLeft: 'auto' }} />
              </div>
              <div style={{ fontSize: 11, color: 'var(--text-primary)' }}>
                {check.detail}
              </div>
            </div>
          );
        })}
      </div>
    </GlassPanel>
  );
}
