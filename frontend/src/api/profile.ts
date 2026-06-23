import { apiRequest } from './client';

export interface ProfileUser {
  id: number;
  username: string;
  email: string;
  role: string;
  created_at: string | null;
}

export const profileApi = {
  getProfile(): Promise<ProfileUser> {
    return apiRequest<ProfileUser>('/api/users/me');
  },

  updateProfile(input: { email?: string }): Promise<ProfileUser> {
    return apiRequest<ProfileUser>('/api/users/me', {
      method: 'PUT',
      body: JSON.stringify(input),
    });
  },

  changePassword(input: {
    current_password: string;
    new_password: string;
  }): Promise<{ message: string }> {
    return apiRequest<{ message: string }>('/api/users/me/password', {
      method: 'PUT',
      body: JSON.stringify(input),
    });
  },
};
