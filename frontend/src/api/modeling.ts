import type { ProblemModeling } from '../types/modeling';
import { apiRequest } from './client';

export const modelingApi = {
  async getByTaskId(taskId: string): Promise<ProblemModeling> {
    const res = await apiRequest<{ data: ProblemModeling }>(`/api/modeling/${taskId}`);
    return res.data;
  },

  async generate(taskId: string): Promise<ProblemModeling> {
    const res = await apiRequest<{ data: ProblemModeling }>(`/api/modeling/${taskId}/generate`, {
      method: 'POST',
    });
    return res.data;
  },
};
