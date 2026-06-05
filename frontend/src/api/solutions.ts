import type { Solution } from '../types/solution';
import { apiRequest } from './client';

export const solutionsApi = {
  async getByTaskId(taskId: string): Promise<Solution[]> {
    const res = await apiRequest<{ data: Solution[] }>(`/api/solutions/${taskId}`);
    return res.data;
  },

  async getDetail(taskId: string, solutionId: string): Promise<Solution> {
    const res = await apiRequest<{ data: Solution }>(`/api/solutions/${taskId}/${solutionId}`);
    return res.data;
  },

  async updateRating(taskId: string, solutionId: string, rating: number): Promise<Solution> {
    const res = await apiRequest<{ data: Solution }>(`/api/solutions/${taskId}/${solutionId}`, {
      method: 'PUT',
      body: JSON.stringify({ rating }),
    });
    return res.data;
  },
};
