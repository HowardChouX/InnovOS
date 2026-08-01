import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { authApi } from '../../api/auth';
import { Eye, EyeOff, Mail, Lock, Check, Phone, User } from 'lucide-react';

export function RegisterPage() {
  const [phone, setPhone] = useState('');
  const [email, setEmail] = useState('');
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [confirm, setConfirm] = useState('');
  const [showPw, setShowPw] = useState(false);
  const [showConfirm, setShowConfirm] = useState(false);
  const [error, setError] = useState('');
  const navigate = useNavigate();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    if (password !== confirm) {
      setError('两次密码不一致');
      return;
    }
    // 手机号校验（11 位数字，1 开头）
    if (!/^1\d{10}$/.test(phone)) {
      setError('手机号格式不正确（11 位数字，1 开头）');
      return;
    }
    try {
      await authApi.register({
        phone,
        password,
        email: email || undefined,
        username: username || undefined,
      });
      navigate(`/verify-phone?phone=${encodeURIComponent(phone)}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : '注册失败');
    }
  };

  return (
    <div
      className="min-h-screen flex items-center justify-center p-4 bg-slate-950"
      style={{ background: 'radial-gradient(circle at top right, #1a2540 0%, #0b1120 40%)' }}
    >
      <div className="w-full max-w-sm">
        <div className="text-center mb-8">
          <div className="text-transparent bg-gradient-to-r from-cyan-400 to-blue-500 bg-clip-text font-bold text-3xl mb-2">
            InnovOS
          </div>
          <p className="text-slate-400 text-sm">创新智能操作系统</p>
        </div>

        <form
          onSubmit={handleSubmit}
          className="bg-slate-800/60 backdrop-blur-sm border border-slate-700 rounded-xl p-6 space-y-4"
        >
          <h2 className="text-white font-bold text-lg text-center">注册</h2>

          {error && (
            <div className="bg-red-500/10 border border-red-500/30 text-red-400 text-sm rounded-lg px-3 py-2">
              {error}
            </div>
          )}

          {/* Phone (primary identifier) */}
          <div>
            <label className="text-sm text-slate-400 mb-1 block">
              手机号 <span className="text-red-400">*</span>
            </label>
            <div className="relative">
              <Phone className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500" />
              <input
                type="tel"
                required
                value={phone}
                onChange={(e) => setPhone(e.target.value)}
                maxLength={11}
                className="w-full bg-slate-900/50 border border-slate-700 rounded-lg pl-10 pr-3 py-2 text-white placeholder-slate-500 focus:outline-none focus:border-cyan-500 transition-colors"
                placeholder="11 位手机号"
                autoComplete="tel"
              />
            </div>
            <p className="text-xs text-slate-500 mt-1">用于登录与接收短信验证码</p>
          </div>

          {/* Email (notification only) */}
          <div>
            <label className="text-sm text-slate-400 mb-1 block">
              邮箱 <span className="text-red-400">*</span>
            </label>
            <div className="relative">
              <Mail className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500" />
              <input
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="w-full bg-slate-900/50 border border-slate-700 rounded-lg pl-10 pr-3 py-2 text-white placeholder-slate-500 focus:outline-none focus:border-cyan-500 transition-colors"
                placeholder="you@example.com"
                autoComplete="email"
              />
            </div>
            <p className="text-xs text-slate-500 mt-1">用于接收通知（不参与登录）</p>
          </div>

          {/* Username (display name, optional) */}
          <div>
            <label className="text-sm text-slate-400 mb-1 block">用户名（可选）</label>
            <div className="relative">
              <User className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500" />
              <input
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                maxLength={100}
                className="w-full bg-slate-900/50 border border-slate-700 rounded-lg pl-10 pr-3 py-2 text-white placeholder-slate-500 focus:outline-none focus:border-cyan-500 transition-colors"
                placeholder="显示名（可空）"
              />
            </div>
          </div>

          {/* Password */}
          <div>
            <label className="text-sm text-slate-400 mb-1 block">
              密码 <span className="text-red-400">*</span>
            </label>
            <div className="relative">
              <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500" />
              <input
                type={showPw ? 'text' : 'password'}
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                minLength={8}
                className="w-full bg-slate-900/50 border border-slate-700 rounded-lg pl-10 pr-10 py-2 text-white placeholder-slate-500 focus:outline-none focus:border-cyan-500 transition-colors"
                placeholder="至少 8 个字符"
                autoComplete="new-password"
              />
              <button
                type="button"
                onClick={() => setShowPw(!showPw)}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-500 hover:text-slate-300 transition-colors"
              >
                {showPw ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
              </button>
            </div>
          </div>

          {/* Confirm Password */}
          <div>
            <label className="text-sm text-slate-400 mb-1 block">确认密码</label>
            <div className="relative">
              <Check className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500" />
              <input
                type={showConfirm ? 'text' : 'password'}
                required
                value={confirm}
                onChange={(e) => setConfirm(e.target.value)}
                minLength={8}
                className="w-full bg-slate-900/50 border border-slate-700 rounded-lg pl-10 pr-10 py-2 text-white placeholder-slate-500 focus:outline-none focus:border-cyan-500 transition-colors"
                placeholder="再次输入密码"
                autoComplete="new-password"
              />
              <button
                type="button"
                onClick={() => setShowConfirm(!showConfirm)}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-500 hover:text-slate-300 transition-colors"
              >
                {showConfirm ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
              </button>
            </div>
          </div>

          <button
            type="submit"
            className="w-full bg-gradient-to-r from-cyan-500 to-blue-600 text-white py-2 rounded-lg font-medium hover:opacity-90 transition-opacity"
          >
            注册
          </button>

          <p className="text-center text-sm text-slate-500">
            已有账号？{' '}
            <Link to="/login" className="text-cyan-400 hover:text-cyan-300 transition-colors">
              登录
            </Link>
          </p>
        </form>
      </div>
    </div>
  );
}
