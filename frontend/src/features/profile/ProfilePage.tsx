import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuthStore } from '../../store/useAuthStore';
import { profileApi } from '../../api/profile';
import {
  User,
  Mail,
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

  // --- Email editing ---
  const [email, setEmail] = useState(user?.email ?? '');
  const [editingEmail, setEditingEmail] = useState(false);
  const [emailSaving, setEmailSaving] = useState(false);
  const [emailMsg, setEmailMsg] = useState<{ type: 'success' | 'error'; text: string } | null>(
    null,
  );

  // --- Password change ---
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
      await profileApi.changePassword({
        current_password: currentPw,
        new_password: newPw,
      });
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

  const handleLogout = async () => {
    await logout();
    navigate('/login');
  };

  if (!user) return null;

  const roleLabel = user.role === 'admin' ? '管理员' : '普通用户';
  const createdAt = user.created_at
    ? new Date(user.created_at).toLocaleDateString('zh-CN', {
        year: 'numeric',
        month: 'long',
        day: 'numeric',
      })
    : '-';

  return (
    <div className="max-w-2xl mx-auto py-8 px-4 space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-white">个人资料</h1>
        <p className="text-slate-400 text-sm mt-1">管理你的账号信息和安全设置</p>
      </div>

      {/* User Info Card */}
      <div className="bg-slate-800/60 backdrop-blur-sm border border-slate-700 rounded-xl p-6">
        <div className="flex items-center gap-4 mb-6">
          <div className="w-14 h-14 rounded-full bg-gradient-to-br from-cyan-500 to-blue-600 flex items-center justify-center text-white text-xl font-bold flex-shrink-0">
            {user.username?.[0]?.toUpperCase() || '?'}
          </div>
          <div>
            <h2 className="text-white font-semibold text-lg">{user.username}</h2>
            <span className="text-xs text-slate-400">{roleLabel}</span>
          </div>
        </div>

        <div className="space-y-3 text-sm">
          {/* Username */}
          <div className="flex items-center gap-3 py-2 border-b border-slate-700/50">
            <User className="w-4 h-4 text-slate-500 flex-shrink-0" />
            <span className="text-slate-400 w-20 flex-shrink-0">用户名</span>
            <span className="text-slate-200">{user.username}</span>
          </div>

          {/* Email */}
          <div className="flex items-center gap-3 py-2 border-b border-slate-700/50">
            <Mail className="w-4 h-4 text-slate-500 flex-shrink-0" />
            <span className="text-slate-400 w-20 flex-shrink-0">邮箱</span>
            {editingEmail ? (
              <div className="flex items-center gap-2 flex-1">
                <input
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  className="flex-1 bg-slate-900/50 border border-slate-700 rounded-lg px-3 py-1.5 text-sm text-white placeholder-slate-500 focus:outline-none focus:border-cyan-500 transition-colors"
                  placeholder="输入邮箱地址"
                />
                <button
                  onClick={handleSaveEmail}
                  disabled={emailSaving}
                  className="p-1.5 rounded-lg bg-emerald-500/10 border border-emerald-500/30 text-emerald-400 hover:bg-emerald-500/20 transition-colors disabled:opacity-50"
                >
                  {emailSaving ? (
                    <Loader2 className="w-4 h-4 animate-spin" />
                  ) : (
                    <Check className="w-4 h-4" />
                  )}
                </button>
                <button
                  onClick={() => {
                    setEditingEmail(false);
                    setEmail(user.email ?? '');
                    setEmailMsg(null);
                  }}
                  className="p-1.5 rounded-lg bg-slate-700/50 text-slate-400 hover:text-slate-200 transition-colors"
                >
                  <X className="w-4 h-4" />
                </button>
              </div>
            ) : (
              <div className="flex items-center gap-2 flex-1">
                <span className="text-slate-200">{user.email || '-'}</span>
                <button
                  onClick={() => setEditingEmail(true)}
                  className="p-1 rounded text-slate-500 hover:text-cyan-400 transition-colors"
                >
                  <Pencil className="w-3.5 h-3.5" />
                </button>
              </div>
            )}
          </div>

          {/* Role */}
          <div className="flex items-center gap-3 py-2 border-b border-slate-700/50">
            <Shield className="w-4 h-4 text-slate-500 flex-shrink-0" />
            <span className="text-slate-400 w-20 flex-shrink-0">角色</span>
            <span
              className={`text-xs px-2 py-0.5 rounded-full ${
                user.role === 'admin'
                  ? 'bg-blue-500/10 border border-blue-500/30 text-blue-400'
                  : 'bg-slate-700/50 border border-slate-600 text-slate-300'
              }`}
            >
              {roleLabel}
            </span>
          </div>

          {/* Created at */}
          <div className="flex items-center gap-3 py-2">
            <Calendar className="w-4 h-4 text-slate-500 flex-shrink-0" />
            <span className="text-slate-400 w-20 flex-shrink-0">注册时间</span>
            <span className="text-slate-200">{createdAt}</span>
          </div>
        </div>

        {emailMsg && (
          <div
            className={`mt-4 text-sm rounded-lg px-3 py-2 ${
              emailMsg.type === 'success'
                ? 'bg-emerald-500/10 border border-emerald-500/30 text-emerald-400'
                : 'bg-red-500/10 border border-red-500/30 text-red-400'
            }`}
          >
            {emailMsg.text}
          </div>
        )}
      </div>

      {/* Change Password Card */}
      <div className="bg-slate-800/60 backdrop-blur-sm border border-slate-700 rounded-xl p-6">
        <div className="flex items-center gap-2 mb-5">
          <KeyRound className="w-4 h-4 text-cyan-400" />
          <h3 className="text-white font-semibold">修改密码</h3>
        </div>

        <form onSubmit={handleChangePassword} className="space-y-4">
          {/* Current password */}
          <div>
            <label className="text-sm text-slate-400 mb-1 block">当前密码</label>
            <div className="relative">
              <input
                type={showCurrentPw ? 'text' : 'password'}
                value={currentPw}
                onChange={(e) => setCurrentPw(e.target.value)}
                className="w-full bg-slate-900/50 border border-slate-700 rounded-lg px-3 py-2 pr-10 text-white text-sm placeholder-slate-500 focus:outline-none focus:border-cyan-500 transition-colors"
                placeholder="输入当前密码"
              />
              <button
                type="button"
                onClick={() => setShowCurrentPw(!showCurrentPw)}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-500 hover:text-slate-300 transition-colors"
              >
                {showCurrentPw ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
              </button>
            </div>
          </div>

          {/* New password */}
          <div>
            <label className="text-sm text-slate-400 mb-1 block">新密码</label>
            <div className="relative">
              <input
                type={showNewPw ? 'text' : 'password'}
                value={newPw}
                onChange={(e) => setNewPw(e.target.value)}
                minLength={8}
                className="w-full bg-slate-900/50 border border-slate-700 rounded-lg px-3 py-2 pr-10 text-white text-sm placeholder-slate-500 focus:outline-none focus:border-cyan-500 transition-colors"
                placeholder="至少8个字符"
              />
              <button
                type="button"
                onClick={() => setShowNewPw(!showNewPw)}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-500 hover:text-slate-300 transition-colors"
              >
                {showNewPw ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
              </button>
            </div>
          </div>

          {/* Confirm new password */}
          <div>
            <label className="text-sm text-slate-400 mb-1 block">确认新密码</label>
            <input
              type="password"
              value={confirmPw}
              onChange={(e) => setConfirmPw(e.target.value)}
              minLength={8}
              className="w-full bg-slate-900/50 border border-slate-700 rounded-lg px-3 py-2 text-white text-sm placeholder-slate-500 focus:outline-none focus:border-cyan-500 transition-colors"
              placeholder="再次输入新密码"
            />
          </div>

          {pwMsg && (
            <div
              className={`text-sm rounded-lg px-3 py-2 ${
                pwMsg.type === 'success'
                  ? 'bg-emerald-500/10 border border-emerald-500/30 text-emerald-400'
                  : 'bg-red-500/10 border border-red-500/30 text-red-400'
              }`}
            >
              {pwMsg.text}
            </div>
          )}

          <button
            type="submit"
            disabled={pwSaving || !currentPw || !newPw || !confirmPw}
            className="flex items-center gap-2 bg-gradient-to-r from-cyan-500 to-blue-600 text-white px-5 py-2 rounded-lg font-medium text-sm hover:opacity-90 transition-opacity disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {pwSaving ? <Loader2 className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4" />}
            保存密码
          </button>
        </form>
      </div>

      {/* Logout */}
      <div className="bg-slate-800/60 backdrop-blur-sm border border-slate-700 rounded-xl p-6">
        <button
          onClick={handleLogout}
          className="flex items-center gap-2 text-red-400 hover:text-red-300 hover:bg-red-500/10 px-4 py-2 rounded-lg transition-colors text-sm font-medium"
        >
          <LogOut className="w-4 h-4" />
          退出登录
        </button>
      </div>
    </div>
  );
}
