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

  async updateStep(
    taskId: string,
    body: {
      agent_id: string;
      status: string;
      description?: string;
      duration?: string;
      output?: string;
    },
  ): Promise<{ status: string; steps: WorkflowState['steps'] }> {
    const res = await apiRequest<{ data: { status: string; steps: WorkflowState['steps'] } }>(
      `/api/workflow/${taskId}/step`,
      {
        method: 'PUT',
        body: JSON.stringify(body),
      },
    );
    return res.data;
  },

  runDemandPortrait: (taskId: string) =>
    apiRequest<{ data: unknown }>(`/api/workflow-steps/demand/${taskId}/analyze`, {
      method: 'POST',
    }).then((r) => r.data),

  getDemandResults: (taskId: string) =>
    apiRequest<{ data: unknown }>(`/api/workflow-steps/demand/${taskId}/results`).then(
      (r) => r.data,
    ),

  runProblemModeling: (taskId: string) =>
    apiRequest<{ data: unknown }>(`/api/workflow-steps/modeling/${taskId}/analyze`, {
      method: 'POST',
    }).then((r) => r.data),

  getModelingResults: (taskId: string) =>
    apiRequest<{ data: unknown }>(`/api/workflow-steps/modeling/${taskId}/results`).then(
      (r) => r.data,
    ),

  proceed: (taskId: string, ratings?: { demandId: string; score: number }[]) =>
    apiRequest<{ data: unknown }>(`/api/analysis/${taskId}/proceed`, {
      method: 'POST',
      body: ratings ? JSON.stringify({ ratings }) : undefined,
    }).then((r) => r.data),
};
