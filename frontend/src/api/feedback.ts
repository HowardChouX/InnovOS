import type { Feedback, FeedbackCreate } from '../types/feedback';
import { apiRequest } from './client';

export const feedbackApi = {
  async create(body: FeedbackCreate): Promise<Feedback> {
    const res = await apiRequest<{ data: Feedback }>('/api/feedback', {
      method: 'POST',
      body: JSON.stringify(body),
    });
    return res.data;
  },

  async getBySolution(solutionId: string): Promise<Feedback[]> {
    const res = await apiRequest<{ data: Feedback[] }>(
      `/api/feedback/${solutionId}`,
    );
    return res.data;
  },
};
