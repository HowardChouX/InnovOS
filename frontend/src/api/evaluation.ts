import type { Evaluation, EvaluationSummary } from '../types/evaluation';
import { apiRequest } from './client';

export const evaluationApi = {
  async evaluate(solutionId: string): Promise<Evaluation> {
    const res = await apiRequest<{ data: Evaluation }>(
      `/api/evaluation/${solutionId}`,
      { method: 'POST' },
    );
    return res.data;
  },

  async getHistory(solutionId: string): Promise<EvaluationSummary[]> {
    const res = await apiRequest<{ data: EvaluationSummary[] }>(
      `/api/evaluation/${solutionId}/history`,
    );
    return res.data;
  },
};
