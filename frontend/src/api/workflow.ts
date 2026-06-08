import type { WorkflowState } from '../types/workflow';
import { apiRequest } from './client';

export interface WorkflowStatus {
  currentPhase: string;
  currentLabel: string;
  progress: number;
  phaseStatus: Record<string, 'pending' | 'running' | 'completed' | 'failed'>;
  history: Array<{ from: string; event: string; to: string }>;
}

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
    agent_id: string;
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

  getStatus: (taskId: string): Promise<WorkflowStatus> =>
    apiRequest<{ data: WorkflowStatus }>(`/api/workflow/${taskId}/status`).then(r => r.data),

  start: (taskId: string) =>
    apiRequest<{ data: any }>(`/api/workflow/${taskId}/run`, { method: 'POST' }).then(r => r.data),

  submitRatings: (taskId: string, phase: string, ratings: any[]) =>
    apiRequest<{ data: any }>(`/api/workflow/${taskId}/rate`, {
      method: 'POST',
      body: JSON.stringify({ phase, ratings }),
    }).then(r => r.data),

  runDemandPortrait: (taskId: string) =>
    apiRequest<{ data: any }>(`/api/workflow-steps/demand/${taskId}/analyze`, { method: 'POST' }).then(r => r.data),

  getDemandResults: (taskId: string) =>
    apiRequest<{ data: any }>(`/api/workflow-steps/demand/${taskId}/results`).then(r => r.data),

  runProblemModeling: (taskId: string) =>
    apiRequest<{ data: any }>(`/api/workflow-steps/modeling/${taskId}/analyze`, { method: 'POST' }).then(r => r.data),

  getModelingResults: (taskId: string) =>
    apiRequest<{ data: any }>(`/api/workflow-steps/modeling/${taskId}/results`).then(r => r.data),
};
