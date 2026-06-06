import { apiRequest } from './client';

export interface Principle {
  id: number;
  name: string;
  definition: string;
  category: string;
  examples: string[];
  explanation?: string;
}

export const principlesApi = {
  async list(): Promise<Principle[]> {
    const res = await apiRequest<{ data: Principle[] }>('/api/principles');
    return res.data;
  },

  async getById(id: number): Promise<Principle> {
    const res = await apiRequest<{ data: Principle }>(`/api/principles/${id}`);
    return res.data;
  },

  async recommendByTask(taskId: string): Promise<Principle[]> {
    const res = await apiRequest<{ data: Principle[] }>(
      `/api/principles/recommend/by-task?task_id=${taskId}`
    );
    return res.data;
  },
};
