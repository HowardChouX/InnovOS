import { useState, useEffect, useRef } from 'react';
import { Outlet, useNavigate } from 'react-router-dom';
import { Sidebar } from './Sidebar';
import { useAuthStore } from '../../store/useAuthStore';
import { notificationsApi, type Notification } from '../../api/notifications';

export function AppLayout() {
  const user = useAuthStore((s) => s.user);
  const logout = useAuthStore((s) => s.logout);
  const navigate = useNavigate();
  const [showMenu, setShowMenu] = useState(false);

  // Notification state
  const [showNotify, setShowNotify] = useState(false);
  const [notifications, setNotifications] = useState<Notification[]>([]);
  const [unreadCount, setUnreadCount] = useState(0);
  const [notifyLoading, setNotifyLoading] = useState(false);
  const notifyRef = useRef<HTMLDivElement>(null);

  // Fetch unread count periodically
  useEffect(() => {
    if (!user) return;
    const fetchUnread = async () => {
      try {
        const count = await notificationsApi.getUnreadCount();
        setUnreadCount(count);
      } catch {
        // silent fail
      }
    };
    fetchUnread();
    const interval = setInterval(fetchUnread, 30000);
    return () => clearInterval(interval);
  }, [user]);

  // Fetch notifications when panel opens
  useEffect(() => {
    if (!showNotify || !user) return;
    const fetchList = async () => {
      setNotifyLoading(true);
      try {
        const res = await notificationsApi.list({ page: 1, pageSize: 20 });
        setNotifications(res.data);
      } catch {
        setNotifications([]);
      } finally {
        setNotifyLoading(false);
      }
    };
    fetchList();
  }, [showNotify, user]);

  // Close notification panel on outside click
  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (notifyRef.current && !notifyRef.current.contains(e.target as Node)) {
        setShowNotify(false);
      }
    };
    if (showNotify) document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, [showNotify]);

  const [detailNotify, setDetailNotify] = useState<Notification | null>(null);
  const [toast, setToast] = useState<{ msg: string; type: 'error' | 'success' } | null>(null);
  const [deleteConfirmId, setDeleteConfirmId] = useState<number | null>(null);

  const openDetail = async (n: Notification) => {
    if (!n.isRead) {
      try {
        await notificationsApi.markAsRead(n.id);
        setNotifications((prev) =>
          prev.map((item) => (item.id === n.id ? { ...item, isRead: true } : item))
        );
        setUnreadCount((c) => Math.max(0, c - 1));
      } catch {
        // silent
      }
    }
    setDetailNotify(n);
  };

  const handleMarkRead = async (id: number) => {
    try {
      await notificationsApi.markAsRead(id);
      setNotifications((prev) =>
        prev.map((n) => (n.id === id ? { ...n, isRead: true } : n))
      );
      setUnreadCount((c) => Math.max(0, c - 1));
    } catch {
      // silent
    }
  };

  const handleMarkAllRead = async () => {
    try {
      await notificationsApi.markAllAsRead();
      setNotifications((prev) => prev.map((n) => ({ ...n, isRead: true })));
      setUnreadCount(0);
    } catch {
      // silent
    }
  };

  const [clearConfirm, setClearConfirm] = useState(false);

  const handleClearAll = async () => {
    if (!clearConfirm) {
      setClearConfirm(true);
      return;
    }
    try {
      await notificationsApi.clearAll();
      setNotifications([]);
      setUnreadCount(0);
      setClearConfirm(false);
    } catch {
      setToast({ msg: '清空失败', type: 'error' });
      setClearConfirm(false);
    }
  };

  useEffect(() => {
    if (!clearConfirm) return;
    const t = setTimeout(() => setClearConfirm(false), 3000);
    return () => clearTimeout(t);
  }, [clearConfirm]);

  useEffect(() => {
    if (!toast) return;
    const t = setTimeout(() => setToast(null), 3000);
    return () => clearTimeout(t);
  }, [toast]);

  useEffect(() => {
    if (!deleteConfirmId) return;
    const t = setTimeout(() => setDeleteConfirmId(null), 3000);
    return () => clearTimeout(t);
  }, [deleteConfirmId]);

  const handleDeleteNotify = async (id: number, e: React.MouseEvent) => {
    e.stopPropagation();
    if (deleteConfirmId !== id) {
      setDeleteConfirmId(id);
      return;
    }
    try {
      await notificationsApi.delete(id);
      setNotifications((prev) => prev.filter((n) => n.id !== id));
      setUnreadCount((c) => Math.max(0, c - 1));
      if (detailNotify?.id === id) setDetailNotify(null);
      setDeleteConfirmId(null);
    } catch {
      setToast({ msg: '删除失败', type: 'error' });
      setDeleteConfirmId(null);
    }
  };

  const formatTime = (iso: string) => {
    const d = new Date(iso);
    const now = new Date();
    const diff = (now.getTime() - d.getTime()) / 1000;
    if (diff < 60) return '刚刚';
    if (diff < 3600) return `${Math.floor(diff / 60)}分钟前`;
    if (diff < 86400) return `${Math.floor(diff / 3600)}小时前`;
    if (diff < 604800) return `${Math.floor(diff / 86400)}天前`;
    return `${d.getMonth() + 1}-${d.getDate()} ${d.getHours()}:${String(d.getMinutes()).padStart(2, '0')}`;
  };

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

          {/* Notification Bell */}
          <div ref={notifyRef} style={{ position: 'relative' }}>
            <div
              onClick={() => setShowNotify((v) => !v)}
              style={{ position: 'relative', cursor: 'pointer', display: 'flex', alignItems: 'center' }}
            >
              <i className="fa-regular fa-bell" style={{ fontSize: 14 }} />
              {unreadCount > 0 && (
                <span style={{
                  position: 'absolute', top: -6, right: -8,
                  minWidth: 14, height: 14, borderRadius: '50%',
                  background: 'var(--accent-red)', color: '#fff',
                  fontSize: 9, fontWeight: 700, display: 'flex', alignItems: 'center', justifyContent: 'center',
                  padding: '0 3px', boxSizing: 'border-box',
                }}>
                  {unreadCount > 99 ? '99+' : unreadCount}
                </span>
              )}
            </div>

            {showNotify && (
              <div style={{
                position: 'absolute', right: -12, top: 34,
                background: 'var(--bg-card)', border: '1px solid var(--border)',
                borderRadius: 10, width: 340, maxHeight: 420, overflow: 'hidden',
                display: 'flex', flexDirection: 'column', zIndex: 100,
                boxShadow: '0 10px 30px rgba(0,0,0,0.3)',
              }}>
                <div style={{
                  display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                  padding: '10px 14px', borderBottom: '1px solid var(--border-light)',
                }}>
                  <span style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-primary)' }}>
                    通知 {unreadCount > 0 && `(${unreadCount}条未读)`}
                  </span>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                    {unreadCount > 0 && (
                      <button
                        onClick={handleMarkAllRead}
                        style={{
                          fontSize: 11, color: 'var(--accent-blue)', background: 'none', border: 'none',
                          cursor: 'pointer', fontFamily: 'inherit', padding: 0,
                        }}
                      >
                        全部已读
                      </button>
                    )}
                    {notifications.length > 0 && (
                      <button
                        onClick={handleClearAll}
                        style={{
                          fontSize: 11,
                          color: clearConfirm ? '#fff' : 'var(--accent-red)',
                          background: clearConfirm ? 'var(--accent-red)' : 'none',
                          border: 'none',
                          cursor: 'pointer', fontFamily: 'inherit', padding: '2px 8px',
                          borderRadius: 4,
                          transition: 'all 0.15s',
                        }}
                      >
                        {clearConfirm ? '确认清空' : '清空全部'}
                      </button>
                    )}
                  </div>
                </div>

                <div style={{ overflowY: 'auto', flex: 1 }}>
                  {notifyLoading ? (
                    <div style={{ textAlign: 'center', padding: 20, color: 'var(--text-tertiary)', fontSize: 12 }}>
                      加载中...
                    </div>
                  ) : notifications.length === 0 ? (
                    <div style={{ textAlign: 'center', padding: 30, color: 'var(--text-tertiary)', fontSize: 12 }}>
                      <i className="fa-regular fa-bell-slash" style={{ fontSize: 24, marginBottom: 8, display: 'block', opacity: 0.5 }} />
                      暂无通知
                    </div>
                  ) : (
                    notifications.map((n) => (
                      <div
                        key={n.id}
                        onClick={() => openDetail(n)}
                        style={{
                          padding: '10px 14px', borderBottom: '1px solid var(--border-light)',
                          cursor: 'pointer',
                          background: n.isRead ? 'transparent' : 'rgba(59,130,246,0.04)',
                          opacity: n.isRead ? 0.7 : 1,
                          position: 'relative',
                        }}
                      >
                        <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 4 }}>
                          {!n.isRead && (
                            <span style={{
                              width: 6, height: 6, borderRadius: '50%', background: 'var(--accent-red)',
                              flexShrink: 0,
                            }} />
                          )}
                          <span style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-primary)', flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                            {n.title}
                          </span>
                          <span style={{ fontSize: 10, color: 'var(--text-tertiary)', flexShrink: 0 }}>
                            {formatTime(n.createdAt)}
                          </span>
                        </div>
                        <div style={{ fontSize: 11, color: 'var(--text-secondary)', lineHeight: 1.5, paddingLeft: n.isRead ? 0 : 12, paddingRight: 24, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                          {n.content}
                        </div>
                        <button
                          onClick={(e) => handleDeleteNotify(n.id, e)}
                          title={deleteConfirmId === n.id ? '确认删除' : '删除'}
                          style={{
                            position: 'absolute', right: 8, top: '50%', transform: 'translateY(-50%)',
                            borderRadius: 4,
                            background: deleteConfirmId === n.id ? 'var(--accent-red)' : 'rgba(248,113,113,0.1)',
                            border: '1px solid rgba(248,113,113,0.2)',
                            color: deleteConfirmId === n.id ? '#fff' : 'var(--accent-red)',
                            cursor: 'pointer', display: 'flex',
                            alignItems: 'center', justifyContent: 'center', fontSize: 10,
                            opacity: deleteConfirmId === n.id ? 1 : 0, transition: 'opacity 0.15s',
                            padding: deleteConfirmId === n.id ? '2px 6px' : '0',
                            minWidth: deleteConfirmId === n.id ? 'auto' : 22,
                            height: 22,
                          }}
                          onMouseEnter={(e) => { if (deleteConfirmId !== n.id) (e.currentTarget as HTMLButtonElement).style.opacity = '1'; }}
                          onMouseLeave={(e) => { if (deleteConfirmId !== n.id) (e.currentTarget as HTMLButtonElement).style.opacity = '0'; }}
                        >
                          {deleteConfirmId === n.id ? '确认?' : <i className="fa-solid fa-trash-can" />}
                        </button>
                      </div>
                    ))
                  )}
                </div>
              </div>
            )}
          </div>

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

      {/* Notification Detail Modal */}
      {detailNotify && (
        <div style={{
          position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.6)',
          display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 200,
        }} onClick={() => setDetailNotify(null)}>
          <div style={{
            background: 'var(--bg-card)', borderRadius: 12, padding: 24,
            border: '1px solid var(--border)', width: 460, maxWidth: '90vw',
          }} onClick={(e) => e.stopPropagation()}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 12 }}>
              {!detailNotify.isRead && (
                <span style={{
                  width: 8, height: 8, borderRadius: '50%', background: 'var(--accent-red)', flexShrink: 0,
                }} />
              )}
              <span style={{ fontSize: 15, fontWeight: 600, color: 'var(--text-primary)', flex: 1 }}>
                {detailNotify.title}
              </span>
            </div>
            <div style={{
              fontSize: 13, color: 'var(--text-secondary)', lineHeight: 1.7,
              marginBottom: 16, whiteSpace: 'pre-wrap', wordBreak: 'break-word',
            }}>
              {detailNotify.content}
            </div>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              <span style={{ fontSize: 11, color: 'var(--text-tertiary)' }}>
                {formatTime(detailNotify.createdAt)}
              </span>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <button
                  onClick={() => {
                    handleDeleteNotify(detailNotify.id, { stopPropagation: () => {} } as React.MouseEvent);
                  }}
                  style={{
                    padding: '6px 14px', borderRadius: 6, fontSize: 12,
                    background: 'rgba(248,113,113,0.1)', border: '1px solid rgba(248,113,113,0.3)',
                    color: 'var(--accent-red)', cursor: 'pointer', fontFamily: 'inherit',
                  }}
                >
                  删除
                </button>
                <button
                  onClick={() => setDetailNotify(null)}
                  style={{
                    padding: '6px 14px', borderRadius: 6, fontSize: 12,
                    background: 'var(--accent)', border: 'none',
                    color: '#fff', cursor: 'pointer', fontFamily: 'inherit',
                  }}
                >
                  关闭
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
