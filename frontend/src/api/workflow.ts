import type { WorkflowState } from '../types/workflow';
import { apiRequest } from './client';

export const workflowApi = {
  async getByTaskId(taskId: string): Promise<WorkflowState> {
    const res = await apiRequest<{ data: WorkflowState }>(`/api/workflow/${taskId}`);
    return res.data;
  },
};
