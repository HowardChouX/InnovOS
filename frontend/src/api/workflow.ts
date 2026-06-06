import type { WorkflowState } from '../types/workflow';
import { apiRequest } from './client';

export const workflowApi = {
  async getByTaskId(taskId: string): Promise<WorkflowState> {
    const res = await apiRequest<{ data: WorkflowState }>(`/api/workflow/${taskId}`);
    return res.data;
  },

  async create(taskId: string): Promise<WorkflowState> {
    const res = await apiRequest<{ data: WorkflowState }>(`/api/workflow/${taskId}`, {
      method: 'POST',
    });
    return res.data;
  },

  async updateStep(taskId: string, body: {
    agent_type: string;
    status: string;
    description?: string;
    duration?: string;
    output?: string;
  }): Promise<{ status: string; steps: WorkflowState['steps'] }> {
    const res = await apiRequest<{ data: { status: string; steps: WorkflowState['steps'] } }>(
      `/api/workflow/${taskId}/step`,
      {
        method: 'PUT',
        body: JSON.stringify(body),
      },
    );
    return res.data;
  },
};
