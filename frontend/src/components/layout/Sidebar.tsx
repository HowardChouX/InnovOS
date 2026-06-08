import { useState, useEffect } from 'react';
import { useLocation, Link } from 'react-router-dom';
import { NAV_ITEMS } from '../../utils/constants';
import { useAuthStore } from '../../store/useAuthStore';
import { useWorkflowStore } from '../../store/useWorkflowStore';
import { sidebarApi, type SidebarStats } from '../../api/sidebar';

const _PHASE_LABELS: Record<string, string> = {
  demand_portrait: '需求画像',
  problem_modeling: '问题建模',
  patent_search: '专利检索',
  solution_gen: '方案生成',
  evaluation: '方案评估',
};

export function Sidebar() {
  const location = useLocation();
  const isAdmin = useAuthStore((s) => s.isAdmin);
  const [stats, setStats] = useState<SidebarStats | null>(null);
  const { currentPhase, isRunning } = useWorkflowStore();

  useEffect(() => {
    sidebarApi.getStats().then(setStats).catch(() => {});
  }, []);

  const items = [
    ...NAV_ITEMS.filter((item) => !((item.path as string) === '/monitor' && !isAdmin)),
  ];

  return (
    <aside style={{
      width: 180, background: 'var(--bg-panel)', borderRight: '1px solid var(--border-light)',
      display: 'flex', flexDirection: 'column', flexShrink: 0,
    }}>
      <nav style={{ display: 'flex', flexDirection: 'column', gap: 2, padding: '10px 8px', flex: 1 }}>
        {items.map((item) => {
          const active = location.pathname === item.path;
          return (
            <Link key={item.path} to={item.path} style={{
              display: 'flex', alignItems: 'center', gap: 10, padding: '9px 12px',
              borderRadius: 8, textDecoration: 'none', fontSize: 13,
              color: active ? '#fff' : 'var(--text-secondary)',
              background: active ? 'var(--accent)' : 'transparent',
              transition: 'all 0.15s',
            }}
              onMouseOver={(e) => { if (!active) { e.currentTarget.style.background = 'var(--bg-card)'; e.currentTarget.style.color = 'var(--text-primary)'; } }}
              onMouseOut={(e) => { if (!active) { e.currentTarget.style.background = 'transparent'; e.currentTarget.style.color = 'var(--text-secondary)'; } }}
            >
              <i className={`fa-solid ${item.icon}`} style={{ width: 16, textAlign: 'center', fontSize: 12 }} />
              <span>{item.label}</span>
            </Link>
          );
        })}

        {/* 工作流进度 */}
        {isRunning && (
          <div style={{ marginTop: 8, borderTop: '1px solid var(--border-light)', paddingTop: 8 }}>
            <div style={{ fontSize: 10, color: 'var(--text-tertiary)', marginBottom: 6, fontWeight: 600 }}>
              流程进度
            </div>
            {Object.entries(_PHASE_LABELS).map(([phase, label]) => {
              const isCurrent = phase === currentPhase;
              const isDone = Object.keys(_PHASE_LABELS).indexOf(phase) < Object.keys(_PHASE_LABELS).indexOf(currentPhase);
              return (
                <div key={phase} style={{
                  display: 'flex', alignItems: 'center', gap: 6, padding: '3px 8px',
                  fontSize: 11, color: isCurrent ? 'var(--accent-blue)' : isDone ? 'var(--accent-green)' : 'var(--text-tertiary)',
                }}>
                  <i className={`fa-solid ${isDone ? 'fa-check-circle' : isCurrent ? 'fa-spinner fa-spin' : 'fa-circle'}`}
                    style={{ fontSize: 8 }} />
                  <span>{label}</span>
                </div>
              );
            })}
          </div>
        )}

        {/* 管理员模块 */}
        {isAdmin && (
          <div style={{ marginTop: 8, borderTop: '1px solid var(--border-light)', paddingTop: 8 }}>
            <div style={{ fontSize: 10, color: 'var(--text-tertiary)', marginBottom: 6, fontWeight: 600 }}>
              管理员
            </div>
            {[
              { label: '模型服务', path: '/admin/keys', icon: 'fa-server' },
              { label: '用户管理', path: '/admin/users', icon: 'fa-users' },
              { label: '数据监控', path: '/monitor', icon: 'fa-chart-line' },
            ].map((item) => {
              const active = location.pathname === item.path;
              return (
                <Link key={item.path} to={item.path} style={{
                  display: 'flex', alignItems: 'center', gap: 10, padding: '7px 12px',
                  borderRadius: 8, textDecoration: 'none', fontSize: 12,
                  color: active ? '#fff' : 'var(--text-secondary)',
                  background: active ? 'var(--accent)' : 'transparent',
                }}>
                  <i className={`fa-solid ${item.icon}`} style={{ width: 14, textAlign: 'center', fontSize: 11 }} />
                  <span>{item.label}</span>
                </Link>
              );
            })}
          </div>
        )}
      </nav>

      {/* System Status */}
      <div style={{
        padding: '12px', borderTop: '1px solid var(--border-light)',
        fontSize: 11,
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 10, color: 'var(--text-secondary)' }}>
          <span style={{ fontWeight: 600 }}>系统状态</span>
          <span style={{
            display: 'inline-flex', alignItems: 'center', gap: 4,
            color: 'var(--accent-green)', fontSize: 10,
          }}>
            <span style={{ width: 6, height: 6, borderRadius: '50%', background: 'var(--accent-green)' }} />
            运行正常
          </span>
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
          {[
            { label: '今日任务', value: stats?.todayTasks ?? '-' },
            { label: '已完成', value: stats?.completedTasks ?? '-' },
            { label: '进行中', value: stats?.analyzingTasks ?? '-' },
          ].map((item) => (
            <div key={item.label} style={{ display: 'flex', justifyContent: 'space-between', color: 'var(--text-tertiary)' }}>
              <span>{item.label}</span>
              <span style={{ color: 'var(--text-primary)', fontWeight: 500 }}>{item.value}</span>
            </div>
          ))}
          <div style={{ borderTop: '1px solid var(--border-light)', paddingTop: 6, marginTop: 2 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', color: 'var(--text-tertiary)' }}>
              <span>专利数据量</span>
              <span style={{ color: 'var(--text-primary)', fontWeight: 500 }}>{stats?.patentCount?.toLocaleString() ?? '-'}</span>
            </div>
          </div>
        </div>
      </div>
    </aside>
  );
}
