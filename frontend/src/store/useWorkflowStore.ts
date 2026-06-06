import { create } from 'zustand';
import type { WorkflowState } from '../types/workflow';
import { workflowApi } from '../api/workflow';

interface WorkflowStore {
  workflow: WorkflowState | null;
  loading: boolean;
  polling: boolean;
  fetchWorkflow: (taskId: string) => Promise<void>;
  startPolling: (taskId: string) => void;
  stopPolling: () => void;
  reset: () => void;
}

let pollTimer: ReturnType<typeof setInterval> | null = null;

export const useWorkflowStore = create<WorkflowStore>((set, get) => ({
  workflow: null,
  loading: false,
  polling: false,
  fetchWorkflow: async (taskId) => {
    set({ loading: true });
    try {
      const workflow = await workflowApi.getByTaskId(taskId);
      set({ workflow, loading: false });
    } catch {
      set({ loading: false });
    }
  },
  startPolling: (taskId) => {
    get().stopPolling();
    set({ polling: true });

    const poll = async () => {
      try {
        const workflow = await workflowApi.getByTaskId(taskId);
        console.log('Workflow poll:', workflow.status, workflow.steps.map(s => ({ id: s.agentId, status: s.status })));
        set({ workflow });
        if (workflow.status === 'completed' || workflow.status === 'failed') {
          get().stopPolling();
        }
      } catch (err) {
        console.error('Workflow poll error:', err);
      }
    };

    poll();
    pollTimer = setInterval(poll, 2000);
  },
  stopPolling: () => {
    if (pollTimer) {
      clearInterval(pollTimer);
      pollTimer = null;
    }
    set({ polling: false });
  },
  reset: () => {
    get().stopPolling();
    set({ workflow: null });
  },
}));
