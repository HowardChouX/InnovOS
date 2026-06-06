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
        set({ workflow });
        if (workflow.status === 'completed' || workflow.status === 'failed') {
          get().stopPolling();
        }
      } catch {
        // ignore poll errors
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
}));
