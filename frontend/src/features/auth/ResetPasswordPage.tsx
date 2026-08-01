import { useEffect, useState } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { authApi } from '../../api/auth';
import { Eye, EyeOff, Lock, Check, ArrowLeft } from 'lucide-react';

interface LocationState {
  phone?: string;
  code?: string;
}

export function ResetPasswordPage() {
  const location = useLocation();
  const state = location.state as LocationState | null;
  const phone = state?.phone ?? '';
  const code = state?.code ?? '';
  const [password, setPassword] = useState('');
  const [confirm, setConfirm] = useState('');
  const [showPw, setShowPw] = useState(false);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();

  useEffect(() => {
    if (!phone || !code) {
      navigate('/forgot-password', { replace: true });
    }
  }, [phone, code, navigate]);

  if (!phone || !code) {
    return null;
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    if (password !== confirm) {
      setError('两次密码不一致');
      return;
    }
    if (password.length < 8) {
      setError('密码至少 8 个字符');
      return;
    }
    setLoading(true);
    try {
      await authApi.resetPasswordWithSms(phone, code, password);
      navigate('/login?reset=ok');
    } catch (err) {
      setError(err instanceof Error ? err.message : '重置失败，验证码可能已过期');
    } finally {
      setLoading(false);
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
          <h2 className="text-white font-bold text-lg text-center">重置密码</h2>
          <p className="text-slate-400 text-sm text-center -mt-2">输入新密码以完成重置</p>

          {error && (
            <div className="bg-red-500/10 border border-red-500/30 text-red-400 text-sm rounded-lg px-3 py-2">
              {error}
            </div>
          )}

          {/* New Password */}
          <div>
            <label className="text-sm text-slate-400 mb-1 block">新密码</label>
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
            <label className="text-sm text-slate-400 mb-1 block">确认新密码</label>
            <div className="relative">
              <Check className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500" />
              <input
                type={showPw ? 'text' : 'password'}
                required
                value={confirm}
                onChange={(e) => setConfirm(e.target.value)}
                minLength={8}
                className="w-full bg-slate-900/50 border border-slate-700 rounded-lg pl-10 pr-3 py-2 text-white placeholder-slate-500 focus:outline-none focus:border-cyan-500 transition-colors"
                placeholder="再次输入"
                autoComplete="new-password"
              />
            </div>
          </div>

          <button
            type="submit"
            disabled={loading}
            className="w-full bg-gradient-to-r from-cyan-500 to-blue-600 text-white py-2 rounded-lg font-medium hover:opacity-90 transition-opacity disabled:opacity-50"
          >
            {loading ? '重置中…' : '重置密码'}
          </button>

          <p className="text-center text-sm text-slate-500">
            <Link
              to="/login"
              className="inline-flex items-center gap-1 text-cyan-400 hover:text-cyan-300 transition-colors"
            >
              <ArrowLeft className="w-4 h-4" /> 返回登录
            </Link>
          </p>
        </form>
      </div>
    </div>
  );
}
