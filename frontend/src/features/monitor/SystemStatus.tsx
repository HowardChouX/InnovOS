import { useMonitorStore } from '../../store/useMonitorStore';
import { GlassPanel } from '../../components/ui/GlassPanel';

export function SystemStatus() {
  const systemStatus = useMonitorStore((s) => s.systemStatus);

  if (!systemStatus) return null;

  const { memory, cpu, aiStats } = systemStatus;

  return (
    <GlassPanel>
      <div className="card-title">
        系统状态
      </div>

      {/* 第一行：系统信息 */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 10, marginBottom: 12 }}>
        {[
          { label: '运行时间', value: systemStatus.uptime, icon: 'fa-clock', color: 'var(--accent-green)' },
          { label: '数据库', value: systemStatus.dbSize, icon: 'fa-database', color: 'var(--accent-blue)' },
          { label: 'API Keys', value: systemStatus.apiKeys, icon: 'fa-key', color: 'var(--accent-yellow)' },
          { label: '版本', value: systemStatus.version, icon: 'fa-code-branch', color: 'var(--text-secondary)' },
        ].map((item) => (
          <div key={item.label} style={{
            display: 'flex', alignItems: 'center', gap: 8,
            padding: '8px 10px', borderRadius: 6,
            background: 'rgba(0,0,0,0.15)', border: '1px solid var(--border-light)',
          }}>
            <i className={`fa-solid ${item.icon}`} style={{ fontSize: 11, color: item.color }} />
            <div>
              <div style={{ fontSize: 10, color: 'var(--text-tertiary)' }}>{item.label}</div>
              <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-primary)' }}>{item.value}</div>
            </div>
          </div>
        ))}
      </div>

      {/* 第二行：资源监控 */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 10, marginBottom: 12 }}>
        {/* 内存 */}
        <div style={{
          padding: '10px 12px', borderRadius: 6,
          background: 'rgba(0,0,0,0.15)', border: '1px solid var(--border-light)',
        }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 6 }}>
            <span style={{ fontSize: 11, color: 'var(--text-secondary)' }}>
              <i className="fa-solid fa-memory" style={{ marginRight: 4 }} />
              内存
            </span>
            <span style={{
              fontSize: 12, fontWeight: 600,
              color: memory.percent > 80 ? 'var(--accent-red)' : memory.percent > 60 ? 'var(--accent-yellow)' : 'var(--accent-green)',
            }}>
              {memory.percent}%
            </span>
          </div>
          <div style={{ height: 4, borderRadius: 2, background: 'rgba(255,255,255,0.05)', overflow: 'hidden' }}>
            <div style={{
              width: `${memory.percent}%`, height: '100%', borderRadius: 2,
              background: memory.percent > 80 ? 'var(--accent-red)' : memory.percent > 60 ? 'var(--accent-yellow)' : 'var(--accent-green)',
              transition: 'width 0.3s',
            }} />
          </div>
          <div style={{ fontSize: 10, color: 'var(--text-tertiary)', marginTop: 4 }}>
            {memory.used} / {memory.total}
          </div>
        </div>

        {/* CPU */}
        <div style={{
          padding: '10px 12px', borderRadius: 6,
          background: 'rgba(0,0,0,0.15)', border: '1px solid var(--border-light)',
        }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 6 }}>
            <span style={{ fontSize: 11, color: 'var(--text-secondary)' }}>
              <i className="fa-solid fa-microchip" style={{ marginRight: 4 }} />
              CPU
            </span>
            <span style={{
              fontSize: 12, fontWeight: 600,
              color: cpu.usage > 80 ? 'var(--accent-red)' : cpu.usage > 60 ? 'var(--accent-yellow)' : 'var(--accent-green)',
            }}>
              {cpu.usage}%
            </span>
          </div>
          <div style={{ height: 4, borderRadius: 2, background: 'rgba(255,255,255,0.05)', overflow: 'hidden' }}>
            <div style={{
              width: `${cpu.usage}%`, height: '100%', borderRadius: 2,
              background: cpu.usage > 80 ? 'var(--accent-red)' : cpu.usage > 60 ? 'var(--accent-yellow)' : 'var(--accent-green)',
              transition: 'width 0.3s',
            }} />
          </div>
          <div style={{ fontSize: 10, color: 'var(--text-tertiary)', marginTop: 4 }}>
            {cpu.cores} 核心
          </div>
        </div>

        {/* AI 调用 */}
        <div style={{
          padding: '10px 12px', borderRadius: 6,
          background: 'rgba(0,0,0,0.15)', border: '1px solid var(--border-light)',
        }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 6 }}>
            <span style={{ fontSize: 11, color: 'var(--text-secondary)' }}>
              <i className="fa-solid fa-brain" style={{ marginRight: 4 }} />
              AI 调用
            </span>
            <span style={{ fontSize: 12, fontWeight: 600, color: 'var(--accent-purple)' }}>
              {aiStats.totalCalls}
            </span>
          </div>
          <div style={{ display: 'flex', gap: 10, marginTop: 6 }}>
            <div style={{ fontSize: 10 }}>
              <span style={{ color: 'var(--accent-green)' }}>✓ {aiStats.successCalls}</span>
            </div>
            <div style={{ fontSize: 10 }}>
              <span style={{ color: 'var(--accent-red)' }}>✗ {aiStats.failedCalls}</span>
            </div>
          </div>
        </div>
      </div>

      {/* 第三行：数据统计 */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 10 }}>
        {[
          { label: '用户数', value: systemStatus.totalUsers, icon: 'fa-users', color: 'var(--accent-purple)' },
          { label: '任务总数', value: systemStatus.totalTasks, icon: 'fa-list-check', color: 'var(--accent-blue)' },
          { label: '专利数据', value: systemStatus.totalPatents.toLocaleString(), icon: 'fa-file-alt', color: 'var(--accent-cyan)' },
        ].map((item) => (
          <div key={item.label} style={{
            display: 'flex', alignItems: 'center', gap: 8,
            padding: '8px 10px', borderRadius: 6,
            background: 'rgba(0,0,0,0.15)', border: '1px solid var(--border-light)',
          }}>
            <i className={`fa-solid ${item.icon}`} style={{ fontSize: 11, color: item.color }} />
            <div>
              <div style={{ fontSize: 10, color: 'var(--text-tertiary)' }}>{item.label}</div>
              <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-primary)' }}>{item.value}</div>
            </div>
          </div>
        ))}
      </div>
    </GlassPanel>
  );
}
