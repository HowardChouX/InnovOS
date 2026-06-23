import { apiRequest } from './client';

interface AuthUser {
  id: number;
  username: string;
  email: string;
  role: string;
  created_at: string;
}

interface AuthResponse {
  // access_token removed - cookie-based auth
  user: AuthUser;
}

export const authApi = {
  register(username: string, password: string) {
    return apiRequest<AuthResponse>('/api/auth/register', {
      method: 'POST',
      body: JSON.stringify({ username, password }),
    });
  },

  login(username: string, password: string) {
    return apiRequest<AuthResponse>('/api/auth/login', {
      method: 'POST',
      body: JSON.stringify({ username, password }),
    });
  },

  me() {
    return apiRequest<AuthUser>('/api/auth/me');
  },

  logout() {
    return apiRequest<{ message: string }>('/api/auth/logout', { method: 'POST' });
  },
};

export type { AuthUser, AuthResponse };
