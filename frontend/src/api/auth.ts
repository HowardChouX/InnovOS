const BASE = 'http://localhost:8000';

interface AuthUser {
  id: number;
  username: string;
  role: string;
  created_at: string;
}

interface AuthResponse {
  access_token: string;
  user: AuthUser;
}

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
    return request<AuthResponse>(
      '/api/auth/register',
      { method: 'POST', body: JSON.stringify({ username, password }) }
    );
  },

  login(username: string, password: string) {
    return request<AuthResponse>(
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

export type { AuthUser, AuthResponse };
