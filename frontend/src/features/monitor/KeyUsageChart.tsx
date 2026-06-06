import { useMonitorStore } from '../../store/useMonitorStore';
import { GlassPanel } from '../../components/ui/GlassPanel';

export function KeyUsageChart() {
  const keyStats = useMonitorStore((s) => s.keyStats);

  if (!keyStats) return null;

  const { totalKeys, activeKeys, totalRequests, keyUsage } = keyStats;
  const maxRequests = Math.max(...keyUsage.map((k) => k.requests), 1);

  return (
    <GlassPanel>
      <div className="card-title">
        <i className="fa-solid fa-key" style={{ fontSize: 12, color: 'var(--accent-yellow)' }} />
        API Key 使用统计
      </div>

      {/* 概览 */}
      <div style={{ display: 'flex', gap: 16, marginBottom: 14 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <span style={{ fontSize: 11, color: 'var(--text-tertiary)' }}>总 Key</span>
          <span style={{ fontSize: 14, fontWeight: 600, color: 'var(--text-primary)' }}>{totalKeys}</span>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <span style={{ fontSize: 11, color: 'var(--text-tertiary)' }}>活跃</span>
          <span style={{ fontSize: 14, fontWeight: 600, color: 'var(--accent-green)' }}>{activeKeys}</span>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <span style={{ fontSize: 11, color: 'var(--text-tertiary)' }}>总请求</span>
          <span style={{ fontSize: 14, fontWeight: 600, color: 'var(--accent-blue)' }}>{totalRequests.toLocaleString()}</span>
        </div>
      </div>

      {/* Key 列表 */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
        {keyUsage.map((k) => (
          <div key={k.id} style={{
            display: 'flex', alignItems: 'center', gap: 10,
            padding: '8px 10px', borderRadius: 6,
            background: 'rgba(0,0,0,0.15)', border: '1px solid var(--border-light)',
          }}>
            <div style={{
              width: 6, height: 6, borderRadius: '50%',
              background: k.isActive ? 'var(--accent-green)' : 'var(--accent-red)',
            }} />
            <span style={{ fontSize: 12, color: 'var(--text-primary)', width: 100, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
              {k.name}
            </span>
            <div style={{ flex: 1, height: 4, borderRadius: 2, background: 'rgba(255,255,255,0.05)' }}>
              <div style={{
                width: `${(k.requests / maxRequests) * 100}%`, height: '100%',
                borderRadius: 2, background: 'var(--accent-blue)',
                transition: 'width 0.3s',
              }} />
            </div>
            <span style={{ fontSize: 11, color: 'var(--text-tertiary)', width: 50, textAlign: 'right' }}>
              {k.requests} 次
            </span>
            <span style={{
              fontSize: 10, padding: '2px 6px', borderRadius: 4,
              background: k.rpm >= k.maxRpm * 0.8 ? 'rgba(248,113,113,0.15)' : 'rgba(74,222,128,0.15)',
              color: k.rpm >= k.maxRpm * 0.8 ? 'var(--accent-red)' : 'var(--accent-green)',
            }}>
              {k.rpm}/{k.maxRpm}
            </span>
          </div>
        ))}
        {keyUsage.length === 0 && (
          <div style={{ textAlign: 'center', padding: 20, fontSize: 12, color: 'var(--text-tertiary)' }}>
            暂无 Key 数据
          </div>
        )}
      </div>
    </GlassPanel>
  );
}
