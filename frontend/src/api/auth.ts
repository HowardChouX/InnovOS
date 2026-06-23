/// <reference types="vite/client" />

// In production (nginx reverse proxy), API is same origin → empty string.
// In development, Vite proxy or explicit URL.
const BASE = import.meta.env.VITE_API_URL ?? '';

interface AuthUser {
  id: number;
  username: string;
  email: string;
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
    credentials: 'include',
    headers: { 'Content-Type': 'application/json', ...options?.headers },
  });
  const data = await res.json();
  if (!res.ok) throw new Error(data.detail || '请求失败');
  return data;
}

export const authApi = {
  register(username: string, password: string) {
    return request<AuthResponse>('/api/auth/register', {
      method: 'POST',
      body: JSON.stringify({ username, password }),
    });
  },

  login(username: string, password: string) {
    return request<AuthResponse>('/api/auth/login', {
      method: 'POST',
      body: JSON.stringify({ username, password }),
    });
  },

  me() {
    return request<AuthUser>('/api/auth/me');
  },

  logout() {
    return request<{ message: string }>('/api/auth/logout', { method: 'POST' });
  },
};

export type { AuthUser, AuthResponse };
