import { create } from 'zustand';
import { authApi } from '../api/auth';

interface User {
  id: number;
  username: string;
  created_at: string;
}

interface AuthStore {
  user: User | null;
  token: string | null;
  loading: boolean;
  login: (username: string, password: string) => Promise<void>;
  register: (username: string, password: string) => Promise<void>;
  logout: () => void;
  init: () => Promise<void>;
}

export const useAuthStore = create<AuthStore>((set) => ({
  user: null,
  token: localStorage.getItem('token'),
  loading: true,

  init: async () => {
    const token = localStorage.getItem('token');
    if (!token) {
      set({ loading: false });
      return;
    }
    try {
      const user = await authApi.me(token);
      set({ user, token, loading: false });
    } catch {
      localStorage.removeItem('token');
      set({ user: null, token: null, loading: false });
    }
  },

  login: async (username, password) => {
    const res = await authApi.login(username, password);
    localStorage.setItem('token', res.access_token);
    set({ user: res.user, token: res.access_token });
  },

  register: async (username, password) => {
    const res = await authApi.register(username, password);
    localStorage.setItem('token', res.access_token);
    set({ user: res.user, token: res.access_token });
  },

  logout: () => {
    localStorage.removeItem('token');
    set({ user: null, token: null });
  },
}));
