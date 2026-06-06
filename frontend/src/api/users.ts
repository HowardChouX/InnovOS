import { apiRequest } from './client';

export interface User {
  id: number;
  username: string;
  email: string;
  role: string;
  isActive: boolean;
  createdAt: string;
}

export interface UpdateUserInput {
  is_active?: boolean;
  role?: string;
}

export const usersApi = {
  async list(): Promise<User[]> {
    const res = await apiRequest<{ data: User[] }>('/api/users');
    return res.data;
  },

  async update(id: number, input: UpdateUserInput): Promise<User> {
    const res = await apiRequest<{ data: User }>(`/api/users/${id}`, {
      method: 'PUT',
      body: JSON.stringify(input),
    });
    return res.data;
  },

  async delete(id: number): Promise<void> {
    await apiRequest(`/api/users/${id}`, { method: 'DELETE' });
  },
};
