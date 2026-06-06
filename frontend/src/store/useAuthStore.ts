import { create } from 'zustand';
import { authApi } from '../api/auth';

interface User {
  id: number;
  username: string;
  role: string;
  created_at: string;
}

interface AuthStore {
  user: User | null;
  token: string | null;
  loading: boolean;
  isAdmin: boolean;
  login: (username: string, password: string) => Promise<void>;
  register: (username: string, password: string) => Promise<void>;
  logout: () => void;
  init: () => Promise<void>;
}

export const useAuthStore = create<AuthStore>((set) => ({
  user: null,
  token: localStorage.getItem('token'),
  loading: true,
  isAdmin: false,

  init: async () => {
    const token = localStorage.getItem('token');
    if (!token) {
      set({ loading: false });
      return;
    }
    try {
      const user = await authApi.me(token);
      set({ user, token, isAdmin: user.role === 'admin', loading: false });
    } catch {
      localStorage.removeItem('token');
      set({ user: null, token: null, isAdmin: false, loading: false });
    }
  },

  login: async (username, password) => {
    const res = await authApi.login(username, password);
    localStorage.setItem('token', res.access_token);
    set({ user: res.user, token: res.access_token, isAdmin: res.user.role === 'admin' });
  },

  register: async (username, password) => {
    const res = await authApi.register(username, password);
    localStorage.setItem('token', res.access_token);
    set({ user: res.user, token: res.access_token, isAdmin: res.user.role === 'admin' });
  },

  logout: () => {
    localStorage.removeItem('token');
    set({ user: null, token: null, isAdmin: false });
  },
}));
