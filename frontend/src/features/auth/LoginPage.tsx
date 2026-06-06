import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuthStore } from '../../store/useAuthStore';

export function LoginPage() {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [showPw, setShowPw] = useState(false);
  const [error, setError] = useState('');
  const login = useAuthStore((s) => s.login);
  const navigate = useNavigate();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    try {
      await login(username, password);
      navigate('/');
    } catch (err) {
      setError(err instanceof Error ? err.message : '登录失败');
    }
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
          <h2 className="text-white font-bold text-lg text-center">登录</h2>
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
                placeholder="输入密码" />
              <span onClick={() => setShowPw(!showPw)}
                style={{ position: 'absolute', right: 10, top: '50%', transform: 'translateY(-50%)', cursor: 'pointer', color: 'var(--text-tertiary)', fontSize: 14 }}>
                <i className={`fa-regular ${showPw ? 'fa-eye-slash' : 'fa-eye'}`} />
              </span>
            </div>
          </div>
          <button type="submit" className="w-full bg-gradient-to-r from-cyan-500 to-blue-600 text-white py-2 rounded-lg font-medium hover:opacity-90 transition">
            登录
          </button>
          <p className="text-center text-sm text-slate-500">没有账号？ <Link to="/register" className="text-cyan-400 hover:text-cyan-300">注册</Link></p>
        </form>
      </div>
    </div>
  );
}
