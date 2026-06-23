import type { ConflictAnalysis } from '../types/analysis';
import { apiRequest } from './client';

export const analysisApi = {
  async getByTaskId(taskId: string): Promise<ConflictAnalysis> {
    const res = await apiRequest<{ data: ConflictAnalysis }>(`/api/analysis/${taskId}`);
    return res.data;
  },

  async triggerAnalysis(
    taskId: string,
    knowledgeBaseIds?: string[],
  ): Promise<{ id: string; taskId: string; status: string }> {
    const body = knowledgeBaseIds ? JSON.stringify({ knowledgeBaseIds }) : null;
    const res = await apiRequest<{ data: { id: string; taskId: string; status: string } }>(
      `/api/analysis/${taskId}/trigger`,
      {
        method: 'POST',
        body,
      },
    );
    return res.data;
  },
};
