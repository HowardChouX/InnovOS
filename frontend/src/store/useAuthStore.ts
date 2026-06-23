import { create } from 'zustand';
import { authApi } from '../api/auth';

interface User {
  id: number;
  username: string;
  email: string;
  role: string;
  created_at: string;
}

interface AuthStore {
  user: User | null;
  loading: boolean;
  isAdmin: boolean;
  login: (username: string, password: string) => Promise<void>;
  register: (username: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
  init: () => Promise<void>;
}

export const useAuthStore = create<AuthStore>((set) => ({
  user: null,
  loading: true,
  isAdmin: false,

  init: async () => {
    try {
      // httpOnly cookie is sent automatically by the browser
      const user = await authApi.me();
      set({ user, isAdmin: user.role === 'admin', loading: false });
    } catch (e) {
      console.error('[useAuthStore] init failed:', e);
      set({ user: null, isAdmin: false, loading: false });
    }
  },

  login: async (username, password) => {
    const res = await authApi.login(username, password);
    // httpOnly cookie is managed by the browser
    set({ user: res.user, isAdmin: res.user.role === 'admin' });
  },

  register: async (username, password) => {
    const res = await authApi.register(username, password);
    set({ user: res.user, isAdmin: res.user.role === 'admin' });
  },

  logout: async () => {
    try {
      await authApi.logout();
    } catch (e) {
      console.error('[useAuthStore] logout failed:', e);
    }
    set({ user: null, isAdmin: false });
  },
}));
