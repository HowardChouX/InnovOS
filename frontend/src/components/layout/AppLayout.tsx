import { useState, useEffect, useRef, useCallback } from 'react';
import { Outlet, useNavigate, useLocation } from 'react-router-dom';
import { Sidebar } from './Sidebar';
import { useAuthStore } from '../../store/useAuthStore';
import { notificationsApi, type Notification } from '../../api/notifications';
import { User, Sun, Moon } from 'lucide-react';

export function AppLayout() {
  const location = useLocation();
  const isKnowledgePage = location.pathname === '/knowledge';
  const user = useAuthStore((s) => s.user);
  const logout = useAuthStore((s) => s.logout);
  const navigate = useNavigate();
  const [showMenu, setShowMenu] = useState(false);

  // Theme toggle
  const [theme, setTheme] = useState<'dark' | 'light'>(
    () => (localStorage.getItem('theme') as 'dark' | 'light') || 'dark',
  );
  const toggleTheme = useCallback(() => {
    setTheme((prev) => {
      const next = prev === 'dark' ? 'light' : 'dark';
      localStorage.setItem('theme', next);
      document.documentElement.setAttribute('data-theme', next);
      return next;
    });
  }, []);
  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme);
  }, []);

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
      } catch (e) {
        console.error('[AppLayout] fetchUnreadCount failed:', e);
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
      } catch (e) {
        console.error('[AppLayout] fetchNotifications failed:', e);
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
          prev.map((item) => (item.id === n.id ? { ...item, isRead: true } : item)),
        );
        setUnreadCount((c) => Math.max(0, c - 1));
      } catch (e) {
        console.error('[AppLayout] markAsRead failed:', e);
      }
    }
    setDetailNotify(n);
  };

  const handleMarkAllRead = async () => {
    try {
      await notificationsApi.markAllAsRead();
      setNotifications((prev) => prev.map((n) => ({ ...n, isRead: true })));
      setUnreadCount(0);
    } catch (e) {
      console.error('[AppLayout] markAllAsRead failed:', e);
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
    } catch (e) {
      console.error('[AppLayout] clearAll failed:', e);
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
    } catch (e) {
      console.error('[AppLayout] deleteNotification failed:', e);
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

  const notifyTypeConfig: Record<string, { icon: string; color: string }> = {
    system: { icon: 'fa-solid fa-gear', color: 'var(--text-tertiary)' },
    workflow: { icon: 'fa-solid fa-diagram-project', color: 'var(--accent-blue)' },
    patent: { icon: 'fa-solid fa-file-lines', color: 'var(--accent-purple)' },
    alert: { icon: 'fa-solid fa-triangle-exclamation', color: 'var(--accent-red)' },
  };
  const getNotifyType = (type: string) => notifyTypeConfig[type] || notifyTypeConfig.system;

  return (
    <div className="min-h-screen flex flex-col bg-[var(--bg-dark)]">
      {/* Header */}
      <header className="h-12 bg-[var(--bg-panel)] border-b border-[var(--border-light)] flex items-center justify-between px-4 flex-shrink-0">
        {/* Logo & Brand */}
        <div className="flex items-baseline gap-1.5">
          <span className="text-base font-bold text-[var(--text-primary)]">InnovOS</span>
          <span className="text-[11px] text-[var(--text-tertiary)]">创新智能操作系统</span>
        </div>

        {/* Slogan */}
        <div className="flex items-center gap-5">
          <span className="text-[13px] text-[var(--text-secondary)]">让创新更智能，让想法变方案</span>
        </div>

        {/* Right section */}
        <div className="flex items-center gap-4 text-[13px] text-[var(--text-secondary)]">
          {/* Theme Toggle */}
          <button
            onClick={toggleTheme}
            className="w-7 h-7 rounded-full border border-[var(--border)] flex items-center justify-center text-[var(--text-tertiary)] hover:text-[var(--accent)] hover:border-[var(--accent)] transition-all duration-200 bg-transparent cursor-pointer"
            title={theme === 'dark' ? '切换亮色主题' : '切换暗色主题'}
          >
            {theme === 'dark' ? <Sun size={13} /> : <Moon size={13} />}
          </button>

          {/* Help Guide */}
          <span
            onClick={() => navigate('/guide')}
            className="cursor-pointer flex items-center gap-1"
          >
            <i className="fa-regular fa-circle-question text-xs" />
            使用指南
          </span>

          {/* Notification Bell */}
          <div ref={notifyRef} className="relative">
            <div
              onClick={() => setShowNotify((v) => !v)}
              className="relative cursor-pointer flex items-center"
            >
              <i className="fa-regular fa-bell text-[14px]" />
              {unreadCount > 0 && (
                <span className="absolute -top-1.5 -right-2 min-w-[14px] h-3.5 rounded-full bg-[var(--accent-red)] text-white text-[9px] font-bold flex items-center justify-center px-[3px] box-border">
                  {unreadCount > 99 ? '99+' : unreadCount}
                </span>
              )}
            </div>

            {/* Notification Panel */}
            {showNotify && (
              <div className="absolute -right-3 top-[34px] bg-[var(--bg-card)] border border-[var(--border)] rounded-[10px] w-[340px] max-h-[420px] overflow-hidden flex flex-col z-[100] shadow-[0_10px_30px_rgba(0,0,0,0.3)]">
                {/* Panel Header */}
                <div className="flex items-center justify-between py-2.5 px-3.5 border-b border-[var(--border-light)]">
                  <span className="text-[13px] font-semibold text-[var(--text-primary)]">
                    通知 {unreadCount > 0 && `(${unreadCount}条未读)`}
                  </span>
                  <div className="flex items-center gap-2.5">
                    {unreadCount > 0 && (
                      <button
                        onClick={handleMarkAllRead}
                        className="text-[11px] text-[var(--accent-blue)] bg-transparent border-none cursor-pointer p-0 font-inherit"
                      >
                        全部已读
                      </button>
                    )}
                    {notifications.length > 0 && (
                      <button
                        onClick={handleClearAll}
                        className={`text-[11px] bg-transparent border-none cursor-pointer font-inherit py-0.5 px-2 rounded transition-all duration-150 ${
                          clearConfirm
                            ? 'text-white bg-[var(--accent-red)]'
                            : 'text-[var(--accent-red)]'
                        }`}
                      >
                        {clearConfirm ? '确认清空' : '清空全部'}
                      </button>
                    )}
                  </div>
                </div>

                {/* Notification List */}
                <div className="overflow-y-auto flex-1">
                  {notifyLoading ? (
                    <div className="text-center py-5 text-[var(--text-tertiary)] text-xs">
                      加载中...
                    </div>
                  ) : notifications.length === 0 ? (
                    <div className="text-center py-7 text-[var(--text-tertiary)] text-xs">
                      <i className="fa-regular fa-bell-slash text-[24px] mb-2 block opacity-50" />
                      暂无通知
                    </div>
                  ) : (
                    notifications.map((n) => (
                      <div
                        key={n.id}
                        onClick={() => openDetail(n)}
                        className={`py-2.5 px-3.5 border-b border-[var(--border-light)] cursor-pointer relative transition-all ${
                          n.isRead
                            ? 'bg-transparent opacity-70'
                            : 'bg-[rgba(59,130,246,0.04)] opacity-100'
                        }`}
                      >
                        <div className="flex items-center gap-1.5 mb-1">
                          {!n.isRead && (
                            <span className="w-1.5 h-1.5 rounded-full bg-[var(--accent-red)] flex-shrink-0" />
                          )}
                          <i
                            className={`${getNotifyType(n.type).icon} text-[10px] flex-shrink-0`}
                            style={{ color: getNotifyType(n.type).color }}
                          />
                          <span className="text-xs font-semibold text-[var(--text-primary)] flex-1 overflow-hidden text-ellipsis whitespace-nowrap">
                            {n.title}
                          </span>
                          <span className="text-[10px] text-[var(--text-tertiary)] flex-shrink-0">
                            {formatTime(n.createdAt)}
                          </span>
                        </div>
                        <div className="text-[11px] text-[var(--text-secondary)] leading-[1.5] overflow-hidden text-ellipsis whitespace-nowrap pr-6"
                          style={{ paddingLeft: n.isRead ? 0 : 12 }}
                        >
                          {n.content}
                        </div>
                        <button
                          onClick={(e) => handleDeleteNotify(n.id, e)}
                          title={deleteConfirmId === n.id ? '确认删除' : '删除'}
                          className={`absolute right-2 top-1/2 -translate-y-1/2 rounded text-[10px] border flex items-center justify-center transition-opacity duration-150 ${
                            deleteConfirmId === n.id
                              ? 'bg-[var(--accent-red)] border-[var(--accent-red)] text-white opacity-100 px-1.5 min-w-0 h-[22px]'
                              : 'bg-[rgba(248,113,113,0.1)] border-[rgba(248,113,113,0.2)] text-[var(--accent-red)] opacity-0 hover:opacity-100 min-w-[22px] h-[22px]'
                          }`}
                        >
                          {deleteConfirmId === n.id ? (
                            '确认?'
                          ) : (
                            <i className="fa-solid fa-trash-can" />
                          )}
                        </button>
                      </div>
                    ))
                  )}
                </div>
              </div>
            )}
          </div>

          {/* User Menu */}
          <div
            className="flex items-center gap-1.5 cursor-pointer relative"
            onClick={() => setShowMenu(!showMenu)}
          >
            <div className="w-7 h-7 rounded-full bg-gradient-to-br from-[#3b82f6] to-[#6366f1] flex items-center justify-center text-[11px] text-white">
              {user?.username?.[0] || '?'}
            </div>
            <span className="text-xs">{user?.username || '用户'}</span>
            <i className="fa-solid fa-chevron-down text-[8px] text-[var(--text-tertiary)]" />

            {/* User Dropdown Menu */}
            {showMenu && (
              <div className="absolute right-0 top-[34px] bg-[var(--bg-card)] border border-[var(--border)] rounded-lg py-1 min-w-[110px] z-50">
                <button
                  onClick={() => {
                    navigate('/profile');
                    setShowMenu(false);
                  }}
                  className="w-full text-left py-[7px] px-3 text-xs text-[var(--text-primary)] bg-transparent border-none cursor-pointer font-inherit flex items-center gap-1.5"
                >
                  <User size={14} />
                  个人资料
                </button>
                <div className="h-px bg-[var(--border-light)] my-0.5" />
                <button
                  onClick={() => {
                    logout();
                    navigate('/login');
                    setShowMenu(false);
                  }}
                  className="w-full text-left py-[7px] px-3 text-xs text-[var(--accent-red)] bg-transparent border-none cursor-pointer font-inherit"
                >
                  退出登录
                </button>
                </div>
              )}
          </div>
        </div>
      </header>

      {/* Main Content */}
      <div className="flex flex-1 overflow-hidden">
        <Sidebar />
        <main
          className={`flex-1 overflow-y-auto bg-[var(--bg-dark)] flex flex-col ${
            isKnowledgePage ? 'p-0' : 'p-3.5'
          }`}
        >
          <div className="flex flex-col flex-1 min-h-0">
            <Outlet />
          </div>
        </main>
      </div>

      {/* Notification Detail Modal */}
      {detailNotify && (
        <div
          className="fixed inset-0 bg-[rgba(0,0,0,0.6)] flex items-center justify-center z-[200]"
          onClick={() => setDetailNotify(null)}
        >
          <div
            className="bg-[var(--bg-card)] rounded-xl p-6 border border-[var(--border)] w-[460px] max-w-[90vw]"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center gap-2 mb-3">
              {!detailNotify.isRead && (
                <span className="w-2 h-2 rounded-full bg-[var(--accent-red)] flex-shrink-0" />
              )}
              <i
                className={`${getNotifyType(detailNotify.type).icon} text-[13px]`}
                style={{ color: getNotifyType(detailNotify.type).color }}
              />
              <span className="text-[15px] font-semibold text-[var(--text-primary)] flex-1">
                {detailNotify.title}
              </span>
            </div>
            <div className="text-[13px] text-[var(--text-secondary)] leading-[1.7] mb-4 whitespace-pre-wrap break-words">
              {detailNotify.content}
            </div>
            <div className="flex items-center justify-between">
              <span className="text-[11px] text-[var(--text-tertiary)]">
                {formatTime(detailNotify.createdAt)}
              </span>
              <div className="flex items-center gap-2">
                <button
                  onClick={() => {
                    handleDeleteNotify(detailNotify.id, {
                      stopPropagation: () => {},
                    } as React.MouseEvent);
                  }}
                  className="py-1.5 px-3.5 rounded-md text-xs bg-[rgba(248,113,113,0.1)] border border-[rgba(248,113,113,0.3)] text-[var(--accent-red)] cursor-pointer font-inherit"
                >
                  删除
                </button>
                <button
                  onClick={() => setDetailNotify(null)}
                  className="py-1.5 px-3.5 rounded-md text-xs bg-[var(--accent)] border-none text-white cursor-pointer font-inherit"
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
