import { useState, useEffect } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { usersApi, type User } from '../../api/users';
import { notificationsApi } from '../../api/notifications';
import { GlassPanel } from '../../components/ui/GlassPanel';
import { Modal } from '../../components/ui/Modal';
import { InlineConfirmModal } from '../../components/ui/InlineConfirmModal';
import { useAuthStore } from '../../store/useAuthStore';
import {
  Bell,
  Trash2,
  Check,
  Ban,
  X,
  Send,
  Pencil,
  ListChecks,
  CheckCircle2,
  Lightbulb,
  Clock,
  Cpu,
} from 'lucide-react';

type ModalType = 'notify' | 'batchNotify' | 'edit' | null;

export function UserManagementPage() {
  const isAdmin = useAuthStore((s) => s.isAdmin);
  const navigate = useNavigate();

  const [users, setUsers] = useState<User[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set());
  const [modalType, setModalType] = useState<ModalType>(null);
  const [modalUser, setModalUser] = useState<User | null>(null);
  const [notifyTitle, setNotifyTitle] = useState('');
  const [notifyContent, setNotifyContent] = useState('');
  const [sending, setSending] = useState(false);
  const [toast, setToast] = useState<{ msg: string; type: 'error' | 'success' } | null>(null);

  // Confirm dialog state
  const [confirmDialog, setConfirmDialog] = useState<{
    open: boolean;
    title: string;
    message: string;
    color: 'red' | 'blue' | 'yellow' | 'green';
    confirmText?: string;
    onConfirm: () => void;
  } | null>(null);

  // Edit user state
  const [editEmail, setEditEmail] = useState('');
  const [editRole, setEditRole] = useState('');
  const [editIsActive, setEditIsActive] = useState(true);
  const [savingEdit, setSavingEdit] = useState(false);

  const fetchUsers = async () => {
    try {
      const data = await usersApi.list();
      setUsers(data);
    } catch {
      setToast({ msg: '获取用户列表失败', type: 'error' });
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (!isAdmin) {
      navigate('/', { replace: true });
      return;
    }
    usersApi
      .list()
      .then((data) => setUsers(data))
      .catch(() => setToast({ msg: '获取用户列表失败', type: 'error' }))
      .finally(() => setLoading(false));
  }, [isAdmin, navigate]);

  useEffect(() => {
    if (!toast) return;
    const t = setTimeout(() => setToast(null), 3000);
    return () => clearTimeout(t);
  }, [toast]);

  const toggleSelect = (id: number) => {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const toggleSelectAll = () => {
    if (selectedIds.size === users.length) {
      setSelectedIds(new Set());
    } else {
      setSelectedIds(new Set(users.map((u) => u.id)));
    }
  };

  const openConfirm = (
    title: string,
    message: string,
    color: 'red' | 'blue' | 'yellow' | 'green',
    onConfirm: () => void,
    confirmText?: string,
  ) => {
    setConfirmDialog({ open: true, title, message, color, confirmText, onConfirm });
  };

  const closeConfirm = () => setConfirmDialog(null);

  const handleToggleActive = (user: User) => {
    const action = user.isActive ? '禁用' : '启用';
    openConfirm(
      `${action}用户`,
      `确认${action}用户「${user.username}」？`,
      user.isActive ? 'yellow' : 'green',
      async () => {
        try {
          await usersApi.update(user.id, { is_active: !user.isActive });
          setToast({ msg: `${action}成功`, type: 'success' });
          fetchUsers();
        } catch {
          setToast({ msg: `${action}失败`, type: 'error' });
        } finally {
          closeConfirm();
        }
      },
      `确认${action}`,
    );
  };

  const handleBatchToggleActive = (activate: boolean) => {
    if (selectedIds.size === 0) return;
    const action = activate ? '启用' : '禁用';
    openConfirm(
      `批量${action}`,
      `确认${action}选中的 ${selectedIds.size} 个用户？`,
      activate ? 'green' : 'yellow',
      async () => {
        try {
          await Promise.all(
            Array.from(selectedIds).map((id) => usersApi.update(id, { is_active: activate })),
          );
          setSelectedIds(new Set());
          setToast({ msg: `批量${action}成功`, type: 'success' });
          fetchUsers();
        } catch {
          setToast({ msg: `批量${action}失败`, type: 'error' });
        } finally {
          closeConfirm();
        }
      },
      `确认${action}`,
    );
  };

  const handleDelete = (user: User) => {
    openConfirm(
      '删除用户',
      `确认删除用户「${user.username}」？此操作不可撤销。`,
      'red',
      async () => {
        try {
          await usersApi.delete(user.id);
          setToast({ msg: '删除成功', type: 'success' });
          fetchUsers();
        } catch (err) {
          setToast({ msg: err instanceof Error ? err.message : '删除失败', type: 'error' });
        } finally {
          closeConfirm();
        }
      },
      '确认删除',
    );
  };

  const handleBatchDelete = () => {
    if (selectedIds.size === 0) return;
    openConfirm(
      '批量删除',
      `确认删除选中的 ${selectedIds.size} 个用户？此操作不可撤销。`,
      'red',
      async () => {
        try {
          await Promise.all(Array.from(selectedIds).map((id) => usersApi.delete(id)));
          setSelectedIds(new Set());
          setToast({ msg: '批量删除成功', type: 'success' });
          fetchUsers();
        } catch (err) {
          setToast({ msg: err instanceof Error ? err.message : '批量删除失败', type: 'error' });
        } finally {
          closeConfirm();
        }
      },
      '确认删除',
    );
  };

  // ─── Edit User ────────────────────────────────────
  const openEditModal = (user: User) => {
    setModalUser(user);
    setEditEmail(user.email || '');
    setEditRole(user.role);
    setEditIsActive(user.isActive);
    setModalType('edit');
  };

  const handleSaveEdit = async () => {
    if (!modalUser) return;
    setSavingEdit(true);
    try {
      await usersApi.update(modalUser.id, {
        email: editEmail.trim(),
        role: editRole,
        is_active: editIsActive,
      });
      setToast({ msg: '用户信息已更新', type: 'success' });
      setModalType(null);
      setModalUser(null);
      fetchUsers();
    } catch (err) {
      setToast({ msg: err instanceof Error ? err.message : '更新失败', type: 'error' });
    } finally {
      setSavingEdit(false);
    }
  };

  // ─── Notify ───────────────────────────────────────
  const openNotifyModal = (user: User | null) => {
    setModalUser(user);
    setModalType(user ? 'notify' : 'batchNotify');
    setNotifyTitle('');
    setNotifyContent('');
  };

  const handleSendNotify = async () => {
    if (!notifyTitle.trim() || !notifyContent.trim()) return;
    setSending(true);
    try {
      if (modalType === 'notify' && modalUser) {
        await notificationsApi.create({
          user_id: modalUser.id,
          title: notifyTitle.trim(),
          content: notifyContent.trim(),
        });
        setToast({ msg: `通知已发送给 ${modalUser.username}`, type: 'success' });
      } else if (modalType === 'batchNotify') {
        const userIds = selectedIds.size > 0 ? Array.from(selectedIds) : undefined;
        const res = await notificationsApi.batchSend({
          title: notifyTitle.trim(),
          content: notifyContent.trim(),
          user_ids: userIds,
        });
        setToast({ msg: `已发送给 ${res.count} 个用户`, type: 'success' });
      }
      setModalType(null);
      setModalUser(null);
    } catch (err) {
      setToast({ msg: err instanceof Error ? err.message : '发送失败', type: 'error' });
    } finally {
      setSending(false);
    }
  };

  const selectedCount = selectedIds.size;
  const allSelected = users.length > 0 && selectedIds.size === users.length;

  return (
    <div className="flex flex-col gap-3.5">
      <GlassPanel>
        {/* Title */}
        <div className="card-title">
          用户管理
          <span className="ml-auto text-[11px] text-slate-500">共 {users.length} 个用户</span>
        </div>

        {/* Batch action bar */}
        {!loading && selectedCount > 0 && (
          <div className="flex items-center gap-2 px-2.5 py-2 mb-2.5 rounded-md bg-blue-500/8 border border-blue-500/20">
            <span className="text-xs text-blue-400">已选 {selectedCount} 项</span>

            <button
              onClick={() => openNotifyModal(null)}
              className="inline-flex items-center gap-1 px-2.5 py-1 rounded text-[11px] bg-blue-500/10 border border-blue-500/20 text-blue-400 hover:bg-blue-500/15 transition-colors cursor-pointer"
            >
              <Bell className="w-3 h-3" />
              群发通知
            </button>

            <button
              onClick={() => handleBatchToggleActive(true)}
              className="inline-flex items-center gap-1 px-2.5 py-1 rounded text-[11px] bg-green-500/10 border border-green-500/20 text-green-400 hover:bg-green-500/15 transition-colors cursor-pointer"
            >
              <Check className="w-3 h-3" />
              批量启用
            </button>

            <button
              onClick={() => handleBatchToggleActive(false)}
              className="inline-flex items-center gap-1 px-2.5 py-1 rounded text-[11px] bg-yellow-500/10 border border-yellow-500/20 text-yellow-400 hover:bg-yellow-500/15 transition-colors cursor-pointer"
            >
              <Ban className="w-3 h-3" />
              批量禁用
            </button>

            <button
              onClick={handleBatchDelete}
              className="inline-flex items-center gap-1 px-2.5 py-1 rounded text-[11px] bg-red-500/10 border border-red-500/20 text-red-400 hover:bg-red-500/15 transition-colors cursor-pointer"
            >
              <Trash2 className="w-3 h-3" />
              批量删除
            </button>

            <button
              onClick={() => setSelectedIds(new Set())}
              className="ml-auto inline-flex items-center gap-1 px-2.5 py-1 rounded text-[11px] bg-slate-500/10 border border-slate-500/20 text-slate-400 hover:bg-slate-500/15 transition-colors cursor-pointer"
            >
              <X className="w-3 h-3" />
              取消选择
            </button>
          </div>
        )}

        {/* Table */}
        {loading ? (
          <div className="text-center py-5 text-slate-500 text-[13px]">加载中...</div>
        ) : (
          <div className="flex flex-col gap-1">
            {/* Header */}
            <div className="flex items-center gap-2.5 px-3 py-1.5 text-[11px] text-slate-500">
              <input
                type="checkbox"
                checked={allSelected}
                onChange={toggleSelectAll}
                className="cursor-pointer accent-blue-500"
              />
              <span className="flex-1">用户名</span>
              <span className="w-[80px]">角色</span>
              <span className="w-[60px]">状态</span>
              <span className="w-[200px] text-right">操作</span>
            </div>

            {/* Rows */}
            {users.map((u) => (
              <div
                key={u.id}
                className={`flex items-center gap-2.5 px-3 py-2 rounded-md border transition-all duration-100 ${
                  selectedIds.has(u.id)
                    ? 'bg-blue-500/8 border-blue-500/20'
                    : 'bg-black/15 border-[var(--border-light)] hover:border-[var(--border)]'
                }`}
              >
                <input
                  type="checkbox"
                  checked={selectedIds.has(u.id)}
                  onChange={() => toggleSelect(u.id)}
                  className="cursor-pointer accent-blue-500"
                />

                {/* Avatar */}
                <div className="w-7 h-7 rounded-full bg-gradient-to-br from-blue-500 to-indigo-500 flex items-center justify-center text-[11px] text-white font-semibold shrink-0">
                  {u.username[0]?.toUpperCase()}
                </div>

                {/* User info */}
                <div className="flex-1 min-w-0">
                  <div className="text-[13px] font-medium text-slate-200 truncate">
                    {u.username}
                  </div>
                  <div className="text-[11px] text-slate-500 truncate">{u.email || '-'}</div>
                  {/* Usage stats */}
                  {u.stats ? (
                    <div className="flex items-center gap-1.5 mt-0.5 flex-wrap text-[11px] text-slate-500">
                      <span className="inline-flex items-center gap-1">
                        <ListChecks className="w-3 h-3 text-slate-500/70" />
                        任务 {u.stats.totalTasks}
                      </span>
                      <span className="text-slate-600">·</span>
                      <span className="inline-flex items-center gap-1">
                        <CheckCircle2 className="w-3 h-3 text-slate-500/70" />
                        完成{' '}
                        {u.stats.totalTasks > 0
                          ? `${Math.round((u.stats.completedTasks / u.stats.totalTasks) * 100)}%`
                          : '-'}
                      </span>
                      <span className="text-slate-600">·</span>
                      <span className="inline-flex items-center gap-1">
                        <Lightbulb className="w-3 h-3 text-slate-500/70" />
                        方案 {u.stats.totalSolutions}
                      </span>
                      {u.stats.lastActive && (
                        <>
                          <span className="text-slate-600">·</span>
                          <span className="inline-flex items-center gap-1 text-slate-500/70">
                            <Clock className="w-3 h-3" />
                            {new Date(u.stats.lastActive).toLocaleDateString('zh-CN', {
                              month: 'numeric',
                              day: 'numeric',
                            })}
                          </span>
                        </>
                      )}
                    </div>
                  ) : (
                    <div className="flex items-center gap-0.5 mt-0.5 text-[11px] text-slate-500/50">
                      暂无使用数据
                    </div>
                  )}
                </div>

                {/* Role badge */}
                <span
                  className={`w-[80px] text-[10px] text-center px-1.5 py-0.5 rounded ${
                    u.role === 'admin'
                      ? 'bg-yellow-500/15 text-yellow-400'
                      : 'bg-slate-500/10 text-slate-500'
                  }`}
                >
                  {u.role === 'admin' ? '管理员' : '普通用户'}
                </span>

                {/* Status badge */}
                <span
                  className={`w-[60px] text-[10px] text-center px-1.5 py-0.5 rounded ${
                    u.isActive ? 'bg-green-500/12 text-green-400' : 'bg-red-500/12 text-red-400'
                  }`}
                >
                  {u.isActive ? '正常' : '禁用'}
                </span>

                {/* Action buttons */}
                <div className="flex gap-1 w-[200px] justify-end">
                  <Link
                    to={`/admin/users/${u.id}/model-services`}
                    className="w-7 h-7 rounded flex items-center justify-center bg-blue-500/10 border border-blue-500/20 text-blue-400 hover:bg-blue-500/15 transition-colors"
                    title="AI 模型服务"
                  >
                    <Cpu className="w-3 h-3" />
                  </Link>
                  <button
                    onClick={() => openEditModal(u)}
                    className="w-7 h-7 rounded flex items-center justify-center bg-slate-500/8 border border-[var(--border-light)] text-slate-400 hover:bg-slate-500/15 hover:text-slate-300 transition-colors cursor-pointer"
                    title="编辑用户"
                  >
                    <Pencil className="w-3 h-3" />
                  </button>
                  <button
                    onClick={() => openNotifyModal(u)}
                    className="w-7 h-7 rounded flex items-center justify-center bg-slate-500/8 border border-[var(--border-light)] text-slate-400 hover:bg-slate-500/15 hover:text-slate-300 transition-colors cursor-pointer"
                    title="发送通知"
                  >
                    <Bell className="w-3 h-3" />
                  </button>
                  <button
                    onClick={() => handleToggleActive(u)}
                    className={`w-7 h-7 rounded flex items-center justify-center bg-slate-500/8 border border-[var(--border-light)] transition-colors cursor-pointer ${
                      u.isActive
                        ? 'text-yellow-400 hover:bg-yellow-500/15'
                        : 'text-green-400 hover:bg-green-500/15'
                    }`}
                    title={u.isActive ? '禁用' : '启用'}
                  >
                    {u.isActive ? <Ban className="w-3 h-3" /> : <Check className="w-3 h-3" />}
                  </button>
                  <button
                    onClick={() => handleDelete(u)}
                    className="w-7 h-7 rounded flex items-center justify-center bg-slate-500/8 border border-[var(--border-light)] text-red-400 hover:bg-red-500/15 transition-colors cursor-pointer"
                    title="删除用户"
                  >
                    <Trash2 className="w-3 h-3" />
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </GlassPanel>

      {/* ─── Edit User Modal ──────────────────────── */}
      <Modal
        open={modalType === 'edit'}
        onClose={() => {
          setModalType(null);
          setModalUser(null);
        }}
        title={`编辑用户 — ${modalUser?.username}`}
      >
        <div className="flex flex-col gap-4">
          {/* Email */}
          <div>
            <label className="block text-xs text-slate-400 mb-1">邮箱</label>
            <input
              value={editEmail}
              onChange={(e) => setEditEmail(e.target.value)}
              placeholder="user@example.com"
              className="w-full px-2.5 py-2 rounded-md bg-black/20 border border-[var(--border)] text-[13px] text-slate-200 outline-none focus:border-blue-500 transition-colors font-[inherit]"
            />
          </div>

          {/* Role */}
          <div>
            <label className="block text-xs text-slate-400 mb-1">角色</label>
            <select
              value={editRole}
              onChange={(e) => setEditRole(e.target.value)}
              className="w-full px-2.5 py-2 rounded-md bg-black/20 border border-[var(--border)] text-[13px] text-slate-200 outline-none cursor-pointer font-[inherit]"
            >
              <option value="user">普通用户</option>
              <option value="admin">管理员</option>
            </select>
          </div>

          {/* Active status */}
          <div className="flex items-center gap-3">
            <label className="text-xs text-slate-400">状态</label>
            <button
              type="button"
              onClick={() => setEditIsActive(!editIsActive)}
              className={`relative w-10 h-5 rounded-full transition-colors cursor-pointer ${
                editIsActive ? 'bg-green-500' : 'bg-slate-600'
              }`}
            >
              <div
                className={`absolute top-0.5 w-4 h-4 rounded-full bg-white shadow transition-transform ${
                  editIsActive ? 'translate-x-5' : 'translate-x-0.5'
                }`}
              />
            </button>
            <span className={`text-xs ${editIsActive ? 'text-green-400' : 'text-red-400'}`}>
              {editIsActive ? '正常' : '禁用'}
            </span>
          </div>

          {/* Actions */}
          <div className="flex justify-end gap-2 pt-2">
            <button
              onClick={() => {
                setModalType(null);
                setModalUser(null);
              }}
              className="px-4 py-2 rounded-md text-[13px] bg-slate-500/10 border border-[var(--border-light)] text-slate-400 hover:bg-slate-500/15 transition-colors cursor-pointer font-[inherit]"
            >
              取消
            </button>
            <button
              onClick={handleSaveEdit}
              disabled={savingEdit}
              className="px-4 py-2 rounded-md text-[13px] bg-blue-500 border-none text-white hover:bg-blue-600 disabled:opacity-50 transition-colors cursor-pointer font-[inherit]"
            >
              {savingEdit ? '保存中...' : '保存'}
            </button>
          </div>
        </div>
      </Modal>

      {/* ─── Notify Modal ─────────────────────────── */}
      <Modal
        open={modalType === 'notify' || modalType === 'batchNotify'}
        onClose={() => {
          setModalType(null);
          setModalUser(null);
        }}
        title={
          modalType === 'notify'
            ? `发送通知给 ${modalUser?.username}`
            : `群发通知 (${selectedCount || '全部'} 人)`
        }
      >
        <div className="flex flex-col gap-3">
          <div>
            <label className="block text-xs text-slate-400 mb-1">通知标题</label>
            <input
              value={notifyTitle}
              onChange={(e) => setNotifyTitle(e.target.value)}
              placeholder="输入通知标题"
              className="w-full px-2.5 py-2 rounded-md bg-black/20 border border-[var(--border)] text-[13px] text-slate-200 outline-none focus:border-blue-500 transition-colors font-[inherit]"
            />
          </div>

          <div>
            <label className="block text-xs text-slate-400 mb-1">通知内容</label>
            <textarea
              value={notifyContent}
              onChange={(e) => setNotifyContent(e.target.value)}
              placeholder="输入通知内容"
              rows={4}
              className="w-full px-2.5 py-2 rounded-md bg-black/20 border border-[var(--border)] text-[13px] text-slate-200 outline-none resize-y focus:border-blue-500 transition-colors font-[inherit]"
            />
          </div>

          <div className="flex justify-end gap-2 pt-1">
            <button
              onClick={() => {
                setModalType(null);
                setModalUser(null);
              }}
              className="px-4 py-2 rounded-md text-[13px] bg-slate-500/10 border border-[var(--border-light)] text-slate-400 hover:bg-slate-500/15 transition-colors cursor-pointer font-[inherit]"
            >
              取消
            </button>
            <button
              onClick={handleSendNotify}
              disabled={sending || !notifyTitle.trim() || !notifyContent.trim()}
              className="inline-flex items-center gap-1.5 px-4 py-2 rounded-md text-[13px] bg-blue-500 border-none text-white hover:bg-blue-600 disabled:opacity-50 transition-colors cursor-pointer font-[inherit]"
            >
              <Send className="w-3.5 h-3.5" />
              {sending ? '发送中...' : '发送'}
            </button>
          </div>
        </div>
      </Modal>

      {/* ─── Confirm Dialog ───────────────────────── */}
      <InlineConfirmModal
        open={confirmDialog?.open ?? false}
        title={confirmDialog?.title ?? ''}
        message={confirmDialog?.message ?? ''}
        confirmText={confirmDialog?.confirmText}
        confirmColor={confirmDialog?.color}
        onConfirm={confirmDialog?.onConfirm ?? (() => {})}
        onCancel={closeConfirm}
      />

      {/* ─── Toast ────────────────────────────────── */}
      {toast && (
        <div
          className={`fixed bottom-5 right-5 px-4 py-2.5 rounded-lg text-[13px] z-[9999] backdrop-blur-[10px] ${
            toast.type === 'success'
              ? 'bg-green-500/15 border border-green-500/30 text-green-400'
              : 'bg-red-500/15 border border-red-500/30 text-red-400'
          }`}
        >
          {toast.msg}
        </div>
      )}
    </div>
  );
}
