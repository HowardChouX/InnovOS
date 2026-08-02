import { apiRequest } from './client';

export interface UserStats {
  totalTasks: number;
  completedTasks: number;
  failedTasks: number;
  totalSolutions: number;
  lastActive: string;
}

export interface User {
  id: number;
  username: string;
  email: string;
  isActive: boolean;
  isSuperuser: boolean;
  createdAt: string;
  stats?: UserStats;
}

export interface UpdateUserInput {
  is_active?: boolean;
  is_superuser?: boolean;
  email?: string;
}

export const usersApi = {
  async list(): Promise<User[]> {
    const res = await apiRequest<{ data: User[] }>('/api/admin/users');
    return res.data;
  },

  async update(id: number, input: UpdateUserInput): Promise<User> {
    const res = await apiRequest<{ data: User }>(`/api/admin/users/${id}`, {
      method: 'PUT',
      body: JSON.stringify(input),
    });
    return res.data;
  },

  async delete(id: number): Promise<void> {
    await apiRequest(`/api/admin/users/${id}`, { method: 'DELETE' });
  },
};
