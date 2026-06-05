import type { Task, CreateTaskInput, UpdateTaskInput } from '../types/task';
import { apiRequest } from './client';

export interface PaginatedTasks {
  data: Task[];
  total: number;
  page: number;
  pageSize: number;
  totalPages: number;
}

export const tasksApi = {
  async list(params?: { page?: number; pageSize?: number; search?: string; status?: string }): Promise<PaginatedTasks> {
    const searchParams = new URLSearchParams();
    if (params?.page) searchParams.set('page', String(params.page));
    if (params?.pageSize) searchParams.set('page_size', String(params.pageSize));
    if (params?.search) searchParams.set('search', params.search);
    if (params?.status) searchParams.set('status', params.status);
    const qs = searchParams.toString();
    const res = await apiRequest<PaginatedTasks>(`/api/tasks${qs ? `?${qs}` : ''}`);
    return res;
  },

  async get(id: string): Promise<Task | undefined> {
    const res = await apiRequest<{ data: Task }>(`/api/tasks/${id}`);
    return res.data;
  },

  async create(input: CreateTaskInput): Promise<Task> {
    const res = await apiRequest<{ data: Task }>('/api/tasks', {
      method: 'POST',
      body: JSON.stringify(input),
    });
    return res.data;
  },

  async update(id: string, input: UpdateTaskInput): Promise<Task> {
    const res = await apiRequest<{ data: Task }>(`/api/tasks/${id}`, {
      method: 'PUT',
      body: JSON.stringify(input),
    });
    return res.data;
  },

  async remove(id: string): Promise<void> {
    await apiRequest(`/api/tasks/${id}`, { method: 'DELETE' });
  },
};
