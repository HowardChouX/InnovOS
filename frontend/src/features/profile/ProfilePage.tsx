import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuthStore } from '../../store/useAuthStore';
import { profileApi } from '../../api/profile';
import {
  Shield,
  Calendar,
  Save,
  KeyRound,
  LogOut,
  Check,
  X,
  Loader2,
  Pencil,
  Eye,
  EyeOff,
} from 'lucide-react';

export function ProfilePage() {
  const user = useAuthStore((s) => s.user);
  const logout = useAuthStore((s) => s.logout);
  const navigate = useNavigate();

  const [email, setEmail] = useState(user?.email ?? '');
  const [editingEmail, setEditingEmail] = useState(false);
  const [emailSaving, setEmailSaving] = useState(false);
  const [emailMsg, setEmailMsg] = useState<{ type: 'success' | 'error'; text: string } | null>(null);

  const [currentPw, setCurrentPw] = useState('');
  const [newPw, setNewPw] = useState('');
  const [confirmPw, setConfirmPw] = useState('');
  const [showCurrentPw, setShowCurrentPw] = useState(false);
  const [showNewPw, setShowNewPw] = useState(false);
  const [pwSaving, setPwSaving] = useState(false);
  const [pwMsg, setPwMsg] = useState<{ type: 'success' | 'error'; text: string } | null>(null);

  const handleSaveEmail = async () => {
    setEmailSaving(true);
    setEmailMsg(null);
    try {
      await profileApi.updateProfile({ email });
      setEditingEmail(false);
      setEmailMsg({ type: 'success', text: '邮箱已更新' });
    } catch (err) {
      setEmailMsg({ type: 'error', text: err instanceof Error ? err.message : '更新失败' });
    } finally {
      setEmailSaving(false);
    }
  };

  const handleChangePassword = async (e: React.FormEvent) => {
    e.preventDefault();
    setPwMsg(null);
    if (newPw !== confirmPw) {
      setPwMsg({ type: 'error', text: '两次新密码不一致' });
      return;
    }
    if (newPw.length < 8) {
      setPwMsg({ type: 'error', text: '新密码至少8个字符' });
      return;
    }
    setPwSaving(true);
    try {
      await profileApi.changePassword({ current_password: currentPw, new_password: newPw });
      setPwMsg({ type: 'success', text: '密码已修改' });
      setCurrentPw('');
      setNewPw('');
      setConfirmPw('');
    } catch (err) {
      setPwMsg({ type: 'error', text: err instanceof Error ? err.message : '修改失败' });
    } finally {
      setPwSaving(false);
    }
  };

  if (!user) return null;

  const roleLabel = user.role === 'admin' ? '管理员' : '普通用户';
  const createdAt = (user as any).created_at
    ? new Date((user as any).created_at).toLocaleDateString('zh-CN', { year: 'numeric', month: 'long', day: 'numeric' })
    : '-';

  const inputClass =
    'w-full bg-[var(--bg-root)] border border-[var(--border)] rounded-lg px-3 py-2.5 text-sm text-[var(--text-primary)] placeholder-[var(--text-tertiary)] focus:outline-none focus:border-[var(--accent)] transition-colors';

  const handleLogout = async () => {
    await logout();
    navigate('/login');
  };

  return (
    <div className="max-w-2xl mx-auto py-8 px-4">
      {/* Page header */}
      <h1 className="text-xl font-bold text-[var(--text-primary)] mb-8">个人资料</h1>

      {/* Profile card — avatar + info fields in ONE clean card */}
      <section className="bg-[var(--bg-card)] border border-[var(--border)] rounded-xl overflow-hidden mb-6">
        {/* Top banner area with avatar */}
        <div className="px-6 pt-6 pb-5 flex items-center gap-5">
          <div className="w-16 h-16 rounded-full bg-gradient-to-br from-cyan-500 to-blue-600 flex items-center justify-center text-white text-2xl font-bold flex-shrink-0 shadow-lg shadow-cyan-500/20">
            {user.username?.[0]?.toUpperCase() || '?'}
          </div>
          <div>
            <h2 className="text-lg font-semibold text-[var(--text-primary)]">{user.username}</h2>
            <div className="flex items-center gap-3 mt-1">
              <span
                className={`text-xs px-2 py-0.5 rounded-full ${
                  user.role === 'admin'
                    ? 'bg-blue-500/10 border border-blue-500/30 text-blue-400'
                    : 'bg-[var(--bg-root)] border border-[var(--border)] text-[var(--text-secondary)]'
                }`}
              >
                {roleLabel}
              </span>
              <span className="text-xs text-[var(--text-tertiary)] flex items-center gap-1">
                <Calendar className="w-3 h-3" />
                {createdAt}
              </span>
            </div>
          </div>
        </div>

        {/* Divider */}
        <div className="border-t border-[var(--border)]" />

        {/* Info fields — compact key-value rows */}
        <div className="px-6 py-2">
          {/* Email */}
          <div className="flex items-center py-3.5 border-b border-[var(--border)] last:border-b-0">
            <span className="text-[var(--text-tertiary)] text-sm w-16 flex-shrink-0">邮箱</span>
            {editingEmail ? (
              <div className="flex items-center gap-2 flex-1">
                <input type="email" value={email} onChange={(e) => setEmail(e.target.value)}
                  className={inputClass} placeholder="输入邮箱地址" />
                <button onClick={handleSaveEmail} disabled={emailSaving}
                  className="p-1.5 rounded-lg bg-emerald-500/10 border border-emerald-500/30 text-emerald-400 hover:bg-emerald-500/20 transition-colors disabled:opacity-50">
                  {emailSaving ? <Loader2 className="w-4 h-4 animate-spin" /> : <Check className="w-4 h-4" />}
                </button>
                <button onClick={() => { setEditingEmail(false); setEmail(user.email ?? ''); setEmailMsg(null); }}
                  className="p-1.5 rounded-lg bg-[var(--bg-root)] border border-[var(--border)] text-[var(--text-tertiary)] hover:text-[var(--text-primary)] transition-colors">
                  <X className="w-4 h-4" />
                </button>
              </div>
            ) : (
              <div className="flex items-center justify-between flex-1">
                <span className="text-sm text-[var(--text-primary)]">{user.email || '未设置'}</span>
                <button onClick={() => setEditingEmail(true)}
                  className="text-[var(--text-tertiary)] hover:text-[var(--accent)] transition-colors p-1">
                  <Pencil className="w-3.5 h-3.5" />
                </button>
              </div>
            )}
          </div>

          {emailMsg && (
            <div className={`text-xs rounded-lg px-3 py-2 mt-2 mb-1 ${
              emailMsg.type === 'success'
                ? 'bg-emerald-500/10 border border-emerald-500/30 text-emerald-400'
                : 'bg-red-500/10 border border-red-500/30 text-red-400'
            }`}>{emailMsg.text}</div>
          )}

          {/* Username (read-only) */}
          <div className="flex items-center py-3.5 border-b border-[var(--border)] last:border-b-0">
            <span className="text-[var(--text-tertiary)] text-sm w-16 flex-shrink-0">用户名</span>
            <span className="text-sm text-[var(--text-primary)]">{user.username}</span>
          </div>

          {/* Role (read-only) */}
          <div className="flex items-center py-3.5 border-b border-[var(--border)] last:border-b-0">
            <span className="text-[var(--text-tertiary)] text-sm w-16 flex-shrink-0">角色</span>
            <Shield className="w-3.5 h-3.5 text-[var(--text-tertiary)] mr-1.5" />
            <span className="text-sm text-[var(--text-primary)]">{roleLabel}</span>
          </div>
        </div>
      </section>

      {/* Password card */}
      <section className="bg-[var(--bg-card)] border border-[var(--border)] rounded-xl overflow-hidden mb-4">
        <div className="px-6 pt-5 pb-2">
          <h3 className="text-sm font-semibold text-[var(--text-primary)] flex items-center gap-2">
            <KeyRound className="w-4 h-4 text-[var(--accent)]" />
            修改密码
          </h3>
        </div>
        <form onSubmit={handleChangePassword} className="px-6 pb-5 space-y-4">
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            <div>
              <label className="text-xs text-[var(--text-tertiary)] mb-1.5 block">当前密码</label>
              <div className="relative">
                <input type={showCurrentPw ? 'text' : 'password'} value={currentPw}
                  onChange={(e) => setCurrentPw(e.target.value)}
                  className={`${inputClass} pr-10`} placeholder="输入当前密码" />
                <button type="button" onClick={() => setShowCurrentPw(!showCurrentPw)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-[var(--text-tertiary)] hover:text-[var(--text-secondary)]">
                  {showCurrentPw ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                </button>
              </div>
            </div>
            <div>
              <label className="text-xs text-[var(--text-tertiary)] mb-1.5 block">新密码</label>
              <div className="relative">
                <input type={showNewPw ? 'text' : 'password'} value={newPw}
                  onChange={(e) => setNewPw(e.target.value)} minLength={8}
                  className={`${inputClass} pr-10`} placeholder="至少8个字符" />
                <button type="button" onClick={() => setShowNewPw(!showNewPw)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-[var(--text-tertiary)] hover:text-[var(--text-secondary)]">
                  {showNewPw ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                </button>
              </div>
            </div>
            <div>
              <label className="text-xs text-[var(--text-tertiary)] mb-1.5 block">确认新密码</label>
              <input type="password" value={confirmPw} onChange={(e) => setConfirmPw(e.target.value)}
                minLength={8} className={inputClass} placeholder="再次输入新密码" />
            </div>
          </div>

          {pwMsg && (
            <div className={`text-xs rounded-lg px-3 py-2 ${
              pwMsg.type === 'success'
                ? 'bg-emerald-500/10 border border-emerald-500/30 text-emerald-400'
                : 'bg-red-500/10 border border-red-500/30 text-red-400'
            }`}>{pwMsg.text}</div>
          )}

          <button type="submit"
            disabled={pwSaving || !currentPw || !newPw || !confirmPw}
            className="flex items-center gap-2 bg-gradient-to-r from-cyan-500 to-blue-600 text-white px-4 py-2 rounded-lg font-medium text-sm hover:opacity-90 transition-opacity disabled:opacity-50 disabled:cursor-not-allowed">
            {pwSaving ? <Loader2 className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4" />}
            保存密码
          </button>
        </form>
      </section>

      {/* Logout — subtle, not a full card */}
      <button onClick={handleLogout}
        className="flex items-center gap-2 text-[var(--text-tertiary)] hover:text-red-400 px-2 py-2 rounded-lg transition-colors text-sm">
        <LogOut className="w-3.5 h-3.5" />
        退出登录
      </button>
    </div>
  );
}
