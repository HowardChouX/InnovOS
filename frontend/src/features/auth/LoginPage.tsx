import { useEffect, useMemo, useRef, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuthStore } from '../../store/useAuthStore';
import { authApi } from '../../api/auth';
import { Eye, EyeOff, Phone, Lock } from 'lucide-react';

type Mode = 'password' | 'code';

export function LoginPage() {
  const [mode, setMode] = useState<Mode>('password');
  const [phone, setPhone] = useState('');
  const [password, setPassword] = useState('');
  const [showPw, setShowPw] = useState(false);
  const [error, setError] = useState('');
  const login = useAuthStore((s) => s.login);
  const navigate = useNavigate();

  // 验证码模式状态
  const [digits, setDigits] = useState<string[]>(['', '', '', '', '', '']);
  const [cooldown, setCooldown] = useState(0);
  const [codeSent, setCodeSent] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const refs = useRef<Array<HTMLInputElement | null>>([null, null, null, null, null, null]);
  const code = useMemo(() => digits.join(''), [digits]);

  useEffect(() => {
    if (cooldown <= 0) return;
    const t = setTimeout(() => setCooldown((c) => c - 1), 1000);
    return () => clearTimeout(t);
  }, [cooldown]);

  const validatePhone = () => {
    if (!/^1\d{10}$/.test(phone)) {
      setError('手机号格式不正确（11 位数字，1 开头）');
      return false;
    }
    return true;
  };

  // 密码登录
  const handlePasswordSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    if (!validatePhone()) return;
    try {
      await login(phone, password);
      navigate('/');
    } catch (err) {
      const apiErr = err as { code?: string; message?: string };
      if (apiErr.code === 'LOGIN_USER_NOT_VERIFIED') {
        navigate(`/verify-phone?phone=${encodeURIComponent(phone)}`);
        setError('请先完成手机号验证');
        return;
      }
      setError(apiErr.message || '登录失败');
    }
  };

  // 发送登录验证码
  const sendCode = async () => {
    setError('');
    if (!validatePhone()) return;
    try {
      await authApi.sendSmsCode(phone, 'login');
      setCodeSent(true);
      setCooldown(60);
      setTimeout(() => refs.current[0]?.focus(), 0);
    } catch (e) {
      setError(e instanceof Error ? e.message : '发送失败');
    }
  };

  // 验证码登录
  const handleCodeSubmit = async (full: string) => {
    setSubmitting(true);
    setError('');
    try {
      const user = await authApi.loginWithCode(phone, full);
      // 更新 store（与密码登录一致），确保 isAdmin 状态正确
      const { useAuthStore } = await import('../../store/useAuthStore');
      useAuthStore.setState({ user, isAdmin: user.is_superuser ?? false });
      navigate('/');
    } catch (e) {
      setError(e instanceof Error ? e.message : '登录失败');
      setDigits(['', '', '', '', '', '']);
      refs.current[0]?.focus();
    } finally {
      setSubmitting(false);
    }
  };

  const setDigit = (i: number, v: string) => {
    const ch = v.replace(/\D/g, '').slice(-1);
    const next = digits.map((d, idx) => (idx === i ? ch : d));
    setDigits(next);
    if (ch && i < 5) refs.current[i + 1]?.focus();
    const joined = next.join('');
    if (mode === 'code' && codeSent && joined.length === 6) void handleCodeSubmit(joined);
  };

  const handlePaste = (e: React.ClipboardEvent<HTMLInputElement>) => {
    const text = e.clipboardData.getData('text').replace(/\D/g, '').slice(0, 6);
    if (!text) return;
    e.preventDefault();
    const arr = ['', '', '', '', '', ''];
    for (let i = 0; i < text.length; i++) arr[i] = text[i];
    setDigits(arr);
    refs.current[Math.min(text.length, 5)]?.focus();
    if (mode === 'code' && codeSent && text.length === 6) void handleCodeSubmit(text);
  };

  const switchMode = (m: Mode) => {
    setMode(m);
    setError('');
    setCodeSent(false);
    setDigits(['', '', '', '', '', '']);
  };

  return (
    <div
      className="min-h-screen flex items-center justify-center p-4 bg-slate-950"
      style={{ background: 'radial-gradient(circle at top right, #1a2540 0%, #0b1120 40%)' }}
    >
      <div className="w-full max-w-sm">
        {/* Logo */}
        <div className="text-center mb-8">
          <div className="text-transparent bg-gradient-to-r from-cyan-400 to-blue-500 bg-clip-text font-bold text-3xl mb-2">
            InnovOS
          </div>
          <p className="text-slate-400 text-sm">创新智能操作系统</p>
        </div>

        {/* Form Card */}
        <div className="bg-slate-800/60 backdrop-blur-sm border border-slate-700 rounded-xl p-6 space-y-4">
          <h2 className="text-white font-bold text-lg text-center">登录</h2>

          {/* Mode Tabs */}
          <div className="flex rounded-lg bg-slate-900/50 p-1">
            <button
              type="button"
              onClick={() => switchMode('password')}
              className={`flex-1 py-1.5 rounded-md text-sm font-medium transition-colors ${
                mode === 'password'
                  ? 'bg-slate-700 text-white'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              密码登录
            </button>
            <button
              type="button"
              onClick={() => switchMode('code')}
              className={`flex-1 py-1.5 rounded-md text-sm font-medium transition-colors ${
                mode === 'code' ? 'bg-slate-700 text-white' : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              验证码登录
            </button>
          </div>

          {error && (
            <div className="bg-red-500/10 border border-red-500/30 text-red-400 text-sm rounded-lg px-3 py-2">
              {error}
            </div>
          )}

          {/* Phone (shared) */}
          <div>
            <label className="text-sm text-slate-400 mb-1 block">手机号</label>
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
          </div>

          {mode === 'password' ? (
            <form onSubmit={handlePasswordSubmit} className="space-y-4">
              {/* Password */}
              <div>
                <label className="text-sm text-slate-400 mb-1 block">密码</label>
                <div className="relative">
                  <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500" />
                  <input
                    type={showPw ? 'text' : 'password'}
                    required
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    minLength={8}
                    className="w-full bg-slate-900/50 border border-slate-700 rounded-lg pl-10 pr-10 py-2 text-white placeholder-slate-500 focus:outline-none focus:border-cyan-500 transition-colors"
                    placeholder="输入密码"
                    autoComplete="current-password"
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

              {/* Forgot password */}
              <div className="text-right -mt-1">
                <Link
                  to="/forgot-password"
                  className="text-xs text-slate-400 hover:text-cyan-400 transition-colors"
                >
                  忘记密码？
                </Link>
              </div>

              <button
                type="submit"
                className="w-full bg-gradient-to-r from-cyan-500 to-blue-600 text-white py-2 rounded-lg font-medium hover:opacity-90 transition-opacity"
              >
                登录
              </button>
            </form>
          ) : (
            <div className="space-y-4">
              {!codeSent ? (
                <button
                  type="button"
                  onClick={sendCode}
                  className="w-full bg-gradient-to-r from-cyan-500 to-blue-600 text-white py-2 rounded-lg font-medium hover:opacity-90 transition-opacity"
                >
                  获取验证码
                </button>
              ) : (
                <>
                  <div className="flex justify-between gap-2" onPaste={handlePaste}>
                    {digits.map((d, i) => (
                      <input
                        key={i}
                        ref={(el) => {
                          refs.current[i] = el;
                        }}
                        inputMode="numeric"
                        maxLength={1}
                        value={d}
                        onChange={(e) => setDigit(i, e.target.value)}
                        disabled={submitting}
                        className="w-10 h-12 text-center text-xl text-white bg-slate-900/50 border border-slate-700 rounded-lg focus:outline-none focus:border-cyan-500"
                        aria-label={`验证码第 ${i + 1} 位`}
                      />
                    ))}
                  </div>

                  <button
                    type="button"
                    onClick={sendCode}
                    disabled={cooldown > 0}
                    className="w-full text-sm text-cyan-400 disabled:text-slate-500"
                  >
                    {cooldown > 0 ? `${cooldown}s 后重发` : '重新发送验证码'}
                  </button>

                  <button
                    type="button"
                    onClick={() => code.length === 6 && handleCodeSubmit(code)}
                    disabled={code.length !== 6 || submitting}
                    className="w-full bg-gradient-to-r from-cyan-500 to-blue-600 text-white py-2 rounded-lg font-medium hover:opacity-90 transition-opacity disabled:opacity-50"
                  >
                    {submitting ? '登录中...' : '登录'}
                  </button>
                </>
              )}
            </div>
          )}

          <p className="text-center text-sm text-slate-500">
            没有账号？{' '}
            <Link to="/register" className="text-cyan-400 hover:text-cyan-300 transition-colors">
              注册
            </Link>
          </p>
        </div>
      </div>
    </div>
  );
}
