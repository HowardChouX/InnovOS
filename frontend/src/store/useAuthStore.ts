import { create } from 'zustand';
import { authApi, AuthUser } from '../api/auth';

interface AuthStore {
  user: AuthUser | null;
  loading: boolean;
  isAdmin: boolean;
  /** 邮箱密码登录 */
  login: (email: string, password: string) => Promise<void>;
  /** 注册：email + password + 可选 phone/username（注册后不自动登录，需邮箱验证） */
  register: (
    email: string,
    password: string,
    phone?: string,
    username?: string,
  ) => Promise<void>;
  logout: () => Promise<void>;
  init: () => Promise<void>;
}

export const useAuthStore = create<AuthStore>((set, get) => ({
  user: null,
  loading: true,
  isAdmin: false,

  init: async () => {
    try {
      // httpOnly cookie 由浏览器自动发送
      const user = await authApi.me();
      set({ user, isAdmin: user.is_superuser, loading: false });
    } catch {
      // 401 是预期路径（未登录）
      set({ user: null, isAdmin: false, loading: false });
    }
  },

  login: async (email, password) => {
    await authApi.login(email, password);
    // 登录后拉取最新用户信息
    const user = await authApi.me();
    set({ user, isAdmin: user.is_superuser });
  },

  register: async (email, password, phone, username) => {
    // 注册成功后用户未登录：等待邮箱验证完成后手动登录。
    await authApi.register({ email, password, phone, username });
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
