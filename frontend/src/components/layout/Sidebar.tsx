import { useLocation, Link } from 'react-router-dom';

import { NAV_ITEMS } from '../../utils/constants';
import { useAuthStore } from '../../store/useAuthStore';

export function Sidebar() {
  const location = useLocation();
  const isAdmin = useAuthStore((s) => s.isAdmin);

  const items = [...NAV_ITEMS];

  return (
    <aside
      style={{
        width: 180,
        background: 'var(--bg-panel)',
        borderRight: '1px solid var(--border-light)',
        display: 'flex',
        flexDirection: 'column',
        flexShrink: 0,
      }}
    >
      <nav
        style={{ display: 'flex', flexDirection: 'column', gap: 2, padding: '10px 8px', flex: 1 }}
      >
        {items.map((item) => {
          const active = location.pathname === item.path;
          return (
            <Link
              key={item.path}
              to={item.path}
              style={{
                display: 'block',
                padding: '9px 12px',
                borderRadius: 8,
                textDecoration: 'none',
                fontSize: 13,
                color: active ? '#fff' : 'var(--text-secondary)',
                background: active ? 'var(--accent)' : 'transparent',
                transition: 'all 0.15s',
              }}
              onMouseOver={(e) => {
                if (!active) {
                  e.currentTarget.style.background = 'var(--bg-card)';
                  e.currentTarget.style.color = 'var(--text-primary)';
                }
              }}
              onMouseOut={(e) => {
                if (!active) {
                  e.currentTarget.style.background = 'transparent';
                  e.currentTarget.style.color = 'var(--text-secondary)';
                }
              }}
            >
              <span>{item.label}</span>
            </Link>
          );
        })}

        {/* 管理员模块 */}
        {isAdmin && (
          <div style={{ marginTop: 8, borderTop: '1px solid var(--border-light)', paddingTop: 8 }}>
            <div
              style={{
                fontSize: 11,
                color: 'var(--text-tertiary)',
                marginBottom: 4,
                paddingLeft: 12,
                fontWeight: 500,
                letterSpacing: '0.04em',
              }}
            >
              管理员
            </div>
            {[
              { label: '模型服务', path: '/admin/keys' },
              { label: '用户管理', path: '/admin/users' },
              { label: '专利数据库', path: '/admin/patents' },
            ].map((item) => {
              const active = location.pathname === item.path;
              return (
                <Link
                  key={item.path}
                  to={item.path}
                  style={{
                    display: 'block',
                    padding: '9px 12px',
                    borderRadius: 8,
                    textDecoration: 'none',
                    fontSize: 13,
                    color: active ? '#fff' : 'var(--text-secondary)',
                    background: active ? 'var(--accent)' : 'transparent',
                    transition: 'all 0.15s',
                  }}
                  onMouseOver={(e) => {
                    if (!active) {
                      e.currentTarget.style.background = 'var(--bg-card)';
                      e.currentTarget.style.color = 'var(--text-primary)';
                    }
                  }}
                  onMouseOut={(e) => {
                    if (!active) {
                      e.currentTarget.style.background = 'transparent';
                      e.currentTarget.style.color = 'var(--text-secondary)';
                    }
                  }}
                >
                  <span>{item.label}</span>
                </Link>
              );
            })}
          </div>
        )}
      </nav>
    </aside>
  );
}
