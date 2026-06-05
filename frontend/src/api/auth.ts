const BASE = 'http://localhost:8000';

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    ...options,
    headers: { 'Content-Type': 'application/json', ...options?.headers },
  });
  const data = await res.json();
  if (!res.ok) throw new Error(data.detail || '请求失败');
  return data;
}

export const authApi = {
  register(username: string, password: string) {
    return request<{ access_token: string; user: { id: number; username: string; created_at: string } }>(
      '/api/auth/register',
      { method: 'POST', body: JSON.stringify({ username, password }) }
    );
  },

  login(username: string, password: string) {
    return request<{ access_token: string; user: { id: number; username: string; created_at: string } }>(
      '/api/auth/login',
      { method: 'POST', body: JSON.stringify({ username, password }) }
    );
  },

  me(token: string) {
    return fetch(`${BASE}/api/auth/me`, {
      headers: { Authorization: `Bearer ${token}` },
    }).then(async (r) => {
      if (!r.ok) throw new Error('登录已过期，请重新登录');
      return r.json();
    });
  },
};
