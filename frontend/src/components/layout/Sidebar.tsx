import { useState, useEffect } from 'react';
import { useLocation, Link } from 'react-router-dom';
import { NAV_ITEMS, ROUTES } from '../../utils/constants';
import { useAuthStore } from '../../store/useAuthStore';
import { sidebarApi, type SidebarStats } from '../../api/sidebar';

export function Sidebar() {
  const location = useLocation();
  const isAdmin = useAuthStore((s) => s.isAdmin);
  const [stats, setStats] = useState<SidebarStats | null>(null);

  useEffect(() => {
    sidebarApi.getStats().then(setStats).catch(() => {});
  }, []);

  const items = [
    ...NAV_ITEMS.filter((item) => !(item.path === ROUTES.MONITOR && !isAdmin)),
    ...(isAdmin ? [{ label: 'Key管理', path: '/admin/keys', icon: 'fa-key' }] : []),
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
              {item.path === '/admin/keys' && (
                <span style={{
                  marginLeft: 'auto', fontSize: 9, padding: '1px 5px',
                  background: 'rgba(251,191,36,0.15)', color: 'var(--accent-yellow)',
                  borderRadius: 3,
                }}>
                  Admin
                </span>
              )}
            </Link>
          );
        })}
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
