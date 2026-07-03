import { Link } from 'react-router-dom';

export default function NotFoundPage() {
  return (
    <div className="min-h-screen flex flex-col items-center justify-center bg-[var(--bg-dark)] text-white">
      <h1 className="text-6xl font-bold mb-4">404</h1>
      <p className="text-lg text-[var(--text-secondary)] mb-6">页面不存在</p>
      <Link
        to="/"
        className="px-6 py-2 rounded-lg bg-[var(--accent)] text-white hover:opacity-90 transition-opacity"
      >
        返回首页
      </Link>
    </div>
  );
}
