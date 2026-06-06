import { useState } from 'react';
import { Outlet, useNavigate } from 'react-router-dom';
import { Sidebar } from './Sidebar';
import { useAuthStore } from '../../store/useAuthStore';

export function AppLayout() {
  const user = useAuthStore((s) => s.user);
  const logout = useAuthStore((s) => s.logout);
  const navigate = useNavigate();
  const [showMenu, setShowMenu] = useState(false);

  return (
    <div style={{ minHeight: '100vh', display: 'flex', flexDirection: 'column', background: 'var(--bg-dark)' }}>
      <header style={{
        height: 48, background: 'var(--bg-panel)', borderBottom: '1px solid var(--border-light)',
        display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '0 16px', flexShrink: 0,
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <div style={{
            width: 28, height: 28, borderRadius: 6,
            background: 'linear-gradient(135deg, #3b82f6, #6366f1)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
          }}>
            <i className="fa-solid fa-cube" style={{ color: '#fff', fontSize: 13 }} />
          </div>
          <div style={{ display: 'flex', alignItems: 'baseline', gap: 6 }}>
            <span style={{ fontSize: 16, fontWeight: 700, color: 'var(--text-primary)' }}>InnovOS</span>
            <span style={{ fontSize: 11, color: 'var(--text-tertiary)' }}>创新智能操作系统</span>
          </div>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: 20 }}>
          <span style={{ fontSize: 13, color: 'var(--text-secondary)' }}>让创新更智能，让想法变方案</span>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: 16, fontSize: 13, color: 'var(--text-secondary)' }}>
          <span style={{ cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 4 }}>
            <i className="fa-regular fa-circle-question" style={{ fontSize: 12 }} />
            使用指南
          </span>
          <span style={{ cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 4 }}>
            <i className="fa-solid fa-book" style={{ fontSize: 12 }} />
            知识库
          </span>
          <i className="fa-regular fa-bell" style={{ fontSize: 14, cursor: 'pointer' }} />
          <div
            style={{ display: 'flex', alignItems: 'center', gap: 6, cursor: 'pointer', position: 'relative' }}
            onClick={() => setShowMenu(!showMenu)}
          >
            <div style={{
              width: 28, height: 28, borderRadius: '50%',
              background: 'linear-gradient(135deg, #3b82f6, #6366f1)',
              display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 11, color: '#fff',
            }}>
              {user?.username?.[0] || '?'}
            </div>
            <span style={{ fontSize: 12 }}>{user?.username || '用户'}</span>
            <i className="fa-solid fa-chevron-down" style={{ fontSize: 8, color: 'var(--text-tertiary)' }} />
            {showMenu && (
              <div style={{
                position: 'absolute', right: 0, top: 34, background: 'var(--bg-card)',
                border: '1px solid var(--border)', borderRadius: 8, padding: '4px 0', minWidth: 110, zIndex: 50,
              }}>
                <button onClick={() => { logout(); navigate('/login'); setShowMenu(false); }}
                  style={{ width: '100%', textAlign: 'left', padding: '7px 12px', fontSize: 12, color: 'var(--accent-red)', background: 'none', border: 'none', cursor: 'pointer', fontFamily: 'inherit' }}>
                  退出登录
                </button>
              </div>
            )}
          </div>
        </div>
      </header>

      <div style={{ display: 'flex', flex: 1, overflow: 'hidden' }}>
        <Sidebar />
        <main style={{
          flex: 1, padding: 14, overflowY: 'auto',
          background: 'var(--bg-dark)',
          display: 'flex', flexDirection: 'column',
        }}>
          <div style={{ display: 'flex', flexDirection: 'column', flex: 1, minHeight: 0 }}>
            <Outlet />
          </div>
        </main>
      </div>
    </div>
  );
}
