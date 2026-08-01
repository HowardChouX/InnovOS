import { useEffect, useMemo, useRef, useState } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import { authApi } from '../../api/auth';
import { Smartphone, ShieldCheck } from 'lucide-react';

export function VerifyPhonePage() {
  const [params] = useSearchParams();
  const phone = params.get('phone') ?? '';
  const navigate = useNavigate();
  const [digits, setDigits] = useState<string[]>(['', '', '', '', '', '']);
  const [error, setError] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [cooldown, setCooldown] = useState(60);
  const refs = useRef<Array<HTMLInputElement | null>>([null, null, null, null, null, null]);

  useEffect(() => {
    if (!phone) navigate('/register', { replace: true });
  }, [phone, navigate]);

  useEffect(() => {
    if (cooldown <= 0) return;
    const t = setTimeout(() => setCooldown((c) => c - 1), 1000);
    return () => clearTimeout(t);
  }, [cooldown]);

  const code = useMemo(() => digits.join(''), [digits]);

  useEffect(() => {
    if (code.length === 6) void submit(code);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [code]);

  async function submit(full: string) {
    setSubmitting(true);
    setError('');
    try {
      await authApi.verifySmsCode(phone, full, 'register');
      navigate(`/login?phone=${encodeURIComponent(phone)}`);
    } catch (e) {
      setError(e instanceof Error ? e.message : '验证失败');
      setDigits(['', '', '', '', '', '']);
      refs.current[0]?.focus();
    } finally {
      setSubmitting(false);
    }
  }

  async function resend() {
    if (cooldown > 0) return;
    setError('');
    try {
      await authApi.sendSmsCode(phone, 'register');
      setCooldown(60);
    } catch (e) {
      setError(e instanceof Error ? e.message : '重发失败');
    }
  }

  function setDigit(i: number, v: string) {
    const ch = v.replace(/\D/g, '').slice(-1);
    setDigits((prev) => prev.map((d, idx) => (idx === i ? ch : d)));
    if (ch && i < 5) refs.current[i + 1]?.focus();
  }

  function handlePaste(e: React.ClipboardEvent<HTMLInputElement>) {
    const text = e.clipboardData.getData('text').replace(/\D/g, '').slice(0, 6);
    if (!text) return;
    e.preventDefault();
    const arr = ['', '', '', '', '', ''];
    for (let i = 0; i < text.length; i++) arr[i] = text[i];
    setDigits(arr);
    const next = Math.min(text.length, 5);
    refs.current[next]?.focus();
  }

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
          onSubmit={(e) => {
            e.preventDefault();
            if (code.length === 6) void submit(code);
          }}
          className="bg-slate-800/60 backdrop-blur-sm border border-slate-700 rounded-xl p-6 space-y-4"
        >
          <h2 className="text-white font-bold text-lg text-center">验证手机号</h2>

          {error && (
            <div className="bg-red-500/10 border border-red-500/30 text-red-400 text-sm rounded-lg px-3 py-2">
              {error}
            </div>
          )}

          <div className="flex items-center gap-2 text-slate-300 text-sm">
            <Smartphone className="w-4 h-4" />
            <span>已发送验证码至手机 {phone}</span>
          </div>

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
            onClick={resend}
            disabled={cooldown > 0}
            className="w-full text-sm text-cyan-400 disabled:text-slate-500"
          >
            {cooldown > 0 ? `${cooldown}s 后重发` : '重新发送验证码'}
          </button>

          <button
            type="submit"
            disabled={code.length !== 6 || submitting}
            className="w-full bg-gradient-to-r from-cyan-500 to-blue-600 text-white py-2 rounded-lg font-medium hover:opacity-90 transition-opacity disabled:opacity-50"
          >
            {submitting ? '验证中...' : '验证'}
          </button>

          <p className="text-center text-sm text-slate-500">
            验证遇到问题？{' '}
            <Link to="/register" className="text-cyan-400 hover:text-cyan-300 transition-colors">
              重新注册
            </Link>
          </p>

          <div className="flex items-center gap-2 text-xs text-slate-500">
            <ShieldCheck className="w-3 h-3" />
            <span>5 分钟内有效</span>
          </div>
        </form>
      </div>
    </div>
  );
}
