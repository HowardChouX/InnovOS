import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuthStore } from '../../store/useAuthStore';

export function RegisterPage() {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [confirm, setConfirm] = useState('');
  const [showPw, setShowPw] = useState(false);
  const [showConfirm, setShowConfirm] = useState(false);
  const [error, setError] = useState('');
  const register = useAuthStore((s) => s.register);
  const navigate = useNavigate();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    if (password !== confirm) { setError('两次密码不一致'); return; }
    try { await register(username, password); navigate('/'); }
    catch (err) { setError(err instanceof Error ? err.message : '注册失败'); }
  };

  return (
    <div className="min-h-screen bg-slate-950 flex items-center justify-center p-4"
      style={{ background: 'radial-gradient(circle at top right, #1a2540 0%, #0f172a 40%)' }}>
      <div className="w-full max-w-sm">
        <div className="text-center mb-8">
          <div className="text-transparent bg-gradient-to-r from-cyan-400 to-blue-500 bg-clip-text font-bold text-3xl mb-2">InnovOS</div>
          <p className="text-slate-400 text-sm">创新智能操作系统</p>
        </div>
        <form onSubmit={handleSubmit} className="bg-slate-800/60 backdrop-blur-sm border border-slate-700 rounded-xl p-6 space-y-4">
          <h2 className="text-white font-bold text-lg text-center">注册</h2>
          {error && <div className="bg-red-500/10 border border-red-500/30 text-red-400 text-sm rounded-lg px-3 py-2">{error}</div>}
          <div>
            <label className="text-sm text-slate-400 mb-1 block">用户名</label>
            <input value={username} onChange={(e) => setUsername(e.target.value)}
              className="w-full bg-slate-900/50 border border-slate-700 rounded-lg px-3 py-2 text-white focus:outline-none focus:border-cyan-500"
              placeholder="输入用户名" />
          </div>
          <div>
            <label className="text-sm text-slate-400 mb-1 block">密码</label>
            <div className="relative">
              <input type={showPw ? 'text' : 'password'} value={password} onChange={(e) => setPassword(e.target.value)}
                className="w-full bg-slate-900/50 border border-slate-700 rounded-lg px-3 py-2 text-white focus:outline-none focus:border-cyan-500 pr-10"
                placeholder="至少4个字符" />
              <span onClick={() => setShowPw(!showPw)}
                style={{ position: 'absolute', right: 10, top: '50%', transform: 'translateY(-50%)', cursor: 'pointer', color: 'var(--text-tertiary)', fontSize: 14 }}>
                <i className={`fa-regular ${showPw ? 'fa-eye-slash' : 'fa-eye'}`} />
              </span>
            </div>
          </div>
          <div>
            <label className="text-sm text-slate-400 mb-1 block">确认密码</label>
            <div className="relative">
              <input type={showConfirm ? 'text' : 'password'} value={confirm} onChange={(e) => setConfirm(e.target.value)}
                className="w-full bg-slate-900/50 border border-slate-700 rounded-lg px-3 py-2 text-white focus:outline-none focus:border-cyan-500 pr-10"
                placeholder="再次输入密码" />
              <span onClick={() => setShowConfirm(!showConfirm)}
                style={{ position: 'absolute', right: 10, top: '50%', transform: 'translateY(-50%)', cursor: 'pointer', color: 'var(--text-tertiary)', fontSize: 14 }}>
                <i className={`fa-regular ${showConfirm ? 'fa-eye-slash' : 'fa-eye'}`} />
              </span>
            </div>
          </div>
          <button type="submit" className="w-full bg-gradient-to-r from-cyan-500 to-blue-600 text-white py-2 rounded-lg font-medium hover:opacity-90 transition">注册</button>
          <p className="text-center text-sm text-slate-500">已有账号？ <Link to="/login" className="text-cyan-400 hover:text-cyan-300">登录</Link></p>
        </form>
      </div>
    </div>
  );
}
