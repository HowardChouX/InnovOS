import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { usersApi, type User } from '../../api/users';
import { notificationsApi } from '../../api/notifications';
import { GlassPanel } from '../../components/ui/GlassPanel';
import { useAuthStore } from '../../store/useAuthStore';

type ModalType = 'notify' | 'batchNotify' | null;

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
  const [_error, _setError] = useState<string | null>(null);
  const [toast, setToast] = useState<{ msg: string; type: 'error' | 'success' } | null>(null);
  const [deleteConfirmId, setDeleteConfirmId] = useState<number | null>(null);
  const [batchDeleteConfirm, setBatchDeleteConfirm] = useState(false);
  const [batchToggleConfirm, setBatchToggleConfirm] = useState<'activate' | 'deactivate' | null>(null);

  useEffect(() => {
    if (!isAdmin) {
      navigate('/', { replace: true });
      return;
    }
    fetchUsers();
  }, [isAdmin, navigate]);

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

  useEffect(() => {
    if (!batchDeleteConfirm) return;
    const t = setTimeout(() => setBatchDeleteConfirm(false), 3000);
    return () => clearTimeout(t);
  }, [batchDeleteConfirm]);

  useEffect(() => {
    if (!batchToggleConfirm) return;
    const t = setTimeout(() => setBatchToggleConfirm(null), 3000);
    return () => clearTimeout(t);
  }, [batchToggleConfirm]);

  const fetchUsers = async () => {
    try {
      const data = await usersApi.list();
      setUsers(data);
    } catch (err) {
      console.error('Failed to fetch users', err);
    } finally {
      setLoading(false);
    }
  };

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

  const handleToggleActive = async (user: User) => {
    try {
      await usersApi.update(user.id, { is_active: !user.isActive });
      fetchUsers();
    } catch (err) {
      console.error('Failed to update user', err);
    }
  };

  const handleBatchToggleActive = async (activate: boolean) => {
    if (selectedIds.size === 0) return;
    const expected = activate ? 'activate' : 'deactivate';
    if (batchToggleConfirm !== expected) {
      setBatchToggleConfirm(expected);
      return;
    }
    try {
      await Promise.all(
        Array.from(selectedIds).map((id) => usersApi.update(id, { is_active: activate }))
      );
      setSelectedIds(new Set());
      setBatchToggleConfirm(null);
      fetchUsers();
    } catch (err) {
      console.error('Batch update failed', err);
      setToast({ msg: `${activate ? '启用' : '禁用'}失败`, type: 'error' });
      setBatchToggleConfirm(null);
    }
  };

  const handleDelete = async (user: User) => {
    if (deleteConfirmId !== user.id) {
      setDeleteConfirmId(user.id);
      return;
    }
    try {
      await usersApi.delete(user.id);
      setDeleteConfirmId(null);
      fetchUsers();
    } catch (err) {
      console.error('Failed to delete user', err);
      setToast({ msg: err instanceof Error ? err.message : '删除失败', type: 'error' });
      setDeleteConfirmId(null);
    }
  };

  const handleBatchDelete = async () => {
    if (selectedIds.size === 0) return;
    if (!batchDeleteConfirm) {
      setBatchDeleteConfirm(true);
      return;
    }
    try {
      await Promise.all(
        Array.from(selectedIds).map((id) => usersApi.delete(id))
      );
      setSelectedIds(new Set());
      setBatchDeleteConfirm(false);
      fetchUsers();
    } catch (err) {
      console.error('Batch delete failed', err);
      setToast({ msg: err instanceof Error ? err.message : '批量删除失败', type: 'error' });
      setBatchDeleteConfirm(false);
    }
  };

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
      const msg = err instanceof Error ? err.message : '发送失败';
      setToast({ msg, type: 'error' });
    } finally {
      setSending(false);
    }
  };

  const selectedCount = selectedIds.size;
  const allSelected = users.length > 0 && selectedIds.size === users.length;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
      <GlassPanel>
        <div className="card-title">
          用户管理
          <span style={{ marginLeft: 'auto', fontSize: 11, color: 'var(--text-tertiary)' }}>
            共 {users.length} 个用户
          </span>
        </div>

        {!loading && selectedCount > 0 && (
          <div style={{
            display: 'flex', alignItems: 'center', gap: 8, padding: '8px 10px',
            borderRadius: 6, background: 'rgba(59,130,246,0.08)', border: '1px solid rgba(59,130,246,0.2)',
            marginBottom: 10,
          }}>
            <span style={{ fontSize: 12, color: 'var(--accent-blue)' }}>已选 {selectedCount} 项</span>
            <button onClick={() => openNotifyModal(null)} style={batchBtnStyle}>
              <i className="fa-solid fa-bell" style={{ marginRight: 4 }} />群发通知
            </button>
            <button onClick={() => handleBatchToggleActive(true)} style={{
              ...batchBtnStyle,
              background: batchToggleConfirm === 'activate' ? 'var(--accent-green)' : batchBtnStyle.background,
              color: batchToggleConfirm === 'activate' ? '#fff' : batchBtnStyle.color,
            }}>
              <i className="fa-solid fa-check" style={{ marginRight: 4 }} />
              {batchToggleConfirm === 'activate' ? '确认启用' : '批量启用'}
            </button>
            <button onClick={() => handleBatchToggleActive(false)} style={{
              ...batchBtnStyle,
              background: batchToggleConfirm === 'deactivate' ? 'var(--accent-yellow)' : batchBtnStyle.background,
              color: batchToggleConfirm === 'deactivate' ? '#fff' : 'var(--accent-yellow)',
            }}>
              <i className="fa-solid fa-ban" style={{ marginRight: 4 }} />
              {batchToggleConfirm === 'deactivate' ? '确认禁用' : '批量禁用'}
            </button>
            <button onClick={handleBatchDelete} style={{
              ...batchBtnStyle,
              background: batchDeleteConfirm ? 'var(--accent-red)' : batchBtnStyle.background,
              color: batchDeleteConfirm ? '#fff' : 'var(--accent-red)',
            }}>
              <i className="fa-solid fa-trash-can" style={{ marginRight: 4 }} />
              {batchDeleteConfirm ? '确认删除' : '批量删除'}
            </button>
            <button onClick={() => setSelectedIds(new Set())} style={{...batchBtnStyle, marginLeft: 'auto'}}>
              取消选择
            </button>
          </div>
        )}

        {loading ? (
          <div style={{ textAlign: 'center', padding: 20, color: 'var(--text-tertiary)' }}>加载中...</div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
            <div style={{
              display: 'flex', alignItems: 'center', gap: 10, padding: '6px 12px',
              fontSize: 11, color: 'var(--text-tertiary)',
            }}>
              <input
                type="checkbox"
                checked={allSelected}
                onChange={toggleSelectAll}
                style={{ cursor: 'pointer' }}
              />
              <span style={{ flex: 1 }}>用户名</span>
              <span style={{ width: 80 }}>角色</span>
              <span style={{ width: 60 }}>状态</span>
              <span style={{ width: 200 }}>操作</span>
            </div>
            {users.map((u) => (
              <div key={u.id} style={{
                display: 'flex', alignItems: 'center', gap: 10,
                padding: '8px 12px', borderRadius: 6,
                background: selectedIds.has(u.id) ? 'rgba(59,130,246,0.08)' : 'rgba(0,0,0,0.15)',
                border: selectedIds.has(u.id) ? '1px solid rgba(59,130,246,0.2)' : '1px solid var(--border-light)',
                transition: 'all 0.1s',
              }}>
                <input
                  type="checkbox"
                  checked={selectedIds.has(u.id)}
                  onChange={() => toggleSelect(u.id)}
                  style={{ cursor: 'pointer' }}
                />
                <div style={{
                  width: 28, height: 28, borderRadius: '50%',
                  background: 'linear-gradient(135deg, #3b82f6, #6366f1)',
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  fontSize: 11, color: '#fff', fontWeight: 600, flexShrink: 0,
                }}>
                  {u.username[0]?.toUpperCase()}
                </div>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontSize: 13, fontWeight: 500, color: 'var(--text-primary)' }}>
                    {u.username}
                  </div>
                  <div style={{ fontSize: 11, color: 'var(--text-tertiary)' }}>{u.email || '-'}</div>
                </div>
                <span style={{
                  width: 80, fontSize: 10, padding: '2px 6px', borderRadius: 3, textAlign: 'center',
                  background: u.role === 'admin' ? 'rgba(251,191,36,0.15)' : 'rgba(100,116,139,0.1)',
                  color: u.role === 'admin' ? 'var(--accent-yellow)' : 'var(--text-tertiary)',
                }}>
                  {u.role === 'admin' ? '管理员' : '普通用户'}
                </span>
                <span style={{
                  width: 60, fontSize: 10, padding: '2px 6px', borderRadius: 3, textAlign: 'center',
                  background: u.isActive ? 'rgba(74,222,128,0.12)' : 'rgba(248,113,113,0.12)',
                  color: u.isActive ? 'var(--accent-green)' : 'var(--accent-red)',
                }}>
                  {u.isActive ? '正常' : '禁用'}
                </span>
                <div style={{ display: 'flex', gap: 4, width: 200, justifyContent: 'flex-end' }}>
                  <button onClick={() => openNotifyModal(u)} style={actionBtnStyle}>
                    <i className="fa-solid fa-bell" />
                  </button>
                  <button onClick={() => handleToggleActive(u)} style={{
                    ...actionBtnStyle,
                    color: u.isActive ? 'var(--accent-yellow)' : 'var(--accent-green)',
                  }}>
                    <i className={`fa-solid fa-${u.isActive ? 'ban' : 'check'}`} />
                  </button>
                  <button onClick={() => handleDelete(u)} style={{
                    ...actionBtnStyle,
                    background: deleteConfirmId === u.id ? 'var(--accent-red)' : actionBtnStyle.background,
                    color: deleteConfirmId === u.id ? '#fff' : 'var(--accent-red)',
                  }}>
                    {deleteConfirmId === u.id ? '?' : <i className="fa-solid fa-trash-can" />}
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </GlassPanel>

      {modalType && (
        <div style={{
          position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.6)',
          display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 100,
        }} onClick={() => setModalType(null)}>
          <div style={{
            background: 'var(--bg-card)', borderRadius: 12, padding: 24,
            border: '1px solid var(--border)', width: 420,
          }} onClick={(e) => e.stopPropagation()}>
            <div style={{ fontSize: 16, fontWeight: 600, color: 'var(--text-primary)', marginBottom: 16 }}>
              {modalType === 'notify' ? `发送通知给 ${modalUser?.username}` : `群发通知 (${selectedCount || '全部'} 人)`}
            </div>
            <div style={{ marginBottom: 12 }}>
              <label style={{ fontSize: 12, color: 'var(--text-secondary)', display: 'block', marginBottom: 4 }}>
                通知标题
              </label>
              <input
                value={notifyTitle}
                onChange={(e) => setNotifyTitle(e.target.value)}
                placeholder="输入通知标题"
                style={inputStyle}
              />
            </div>
            <div style={{ marginBottom: 16 }}>
              <label style={{ fontSize: 12, color: 'var(--text-secondary)', display: 'block', marginBottom: 4 }}>
                通知内容
              </label>
              <textarea
                value={notifyContent}
                onChange={(e) => setNotifyContent(e.target.value)}
                placeholder="输入通知内容"
                rows={4}
                style={{ ...inputStyle, resize: 'vertical' }}
              />
            </div>
            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8 }}>
              <button onClick={() => setModalType(null)} style={cancelBtnStyle}>取消</button>
              <button
                onClick={handleSendNotify}
                disabled={sending || !notifyTitle.trim() || !notifyContent.trim()}
                style={{
                  ...confirmBtnStyle,
                  opacity: sending || !notifyTitle.trim() || !notifyContent.trim() ? 0.5 : 1,
                }}
              >
                {sending ? '发送中...' : '发送'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

const batchBtnStyle: React.CSSProperties = {
  padding: '4px 10px', borderRadius: 4, fontSize: 11,
  background: 'rgba(59,130,246,0.1)', border: '1px solid rgba(59,130,246,0.2)',
  color: 'var(--accent-blue)', cursor: 'pointer', fontFamily: 'inherit',
};

const actionBtnStyle: React.CSSProperties = {
  width: 28, height: 28, borderRadius: 4, display: 'flex', alignItems: 'center', justifyContent: 'center',
  background: 'rgba(100,116,139,0.08)', border: '1px solid var(--border-light)',
  color: 'var(--text-secondary)', cursor: 'pointer', fontSize: 11,
};

const inputStyle: React.CSSProperties = {
  width: '100%', padding: '8px 10px', borderRadius: 6,
  background: 'rgba(0,0,0,0.2)', border: '1px solid var(--border-light)',
  color: 'var(--text-primary)', fontSize: 13, outline: 'none', fontFamily: 'inherit',
  boxSizing: 'border-box',
};

const cancelBtnStyle: React.CSSProperties = {
  padding: '8px 16px', borderRadius: 6, fontSize: 13,
  background: 'rgba(100,116,139,0.1)', border: '1px solid var(--border-light)',
  color: 'var(--text-secondary)', cursor: 'pointer', fontFamily: 'inherit',
};

const confirmBtnStyle: React.CSSProperties = {
  padding: '8px 16px', borderRadius: 6, fontSize: 13,
  background: 'var(--accent)', border: 'none',
  color: '#fff', cursor: 'pointer', fontFamily: 'inherit',
};
