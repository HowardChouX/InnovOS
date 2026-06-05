import { create } from 'zustand';
import type { WorkflowState } from '../types/workflow';
import { workflowApi } from '../api/workflow';

interface WorkflowStore {
  workflow: WorkflowState | null;
  loading: boolean;
  fetchWorkflow: (taskId: string) => Promise<void>;
}

export const useWorkflowStore = create<WorkflowStore>((set) => ({
  workflow: null,
  loading: false,
  fetchWorkflow: async (taskId) => {
    set({ loading: true });
    try {
      const workflow = await workflowApi.getByTaskId(taskId);
      set({ workflow, loading: false });
    } catch {
      set({ loading: false });
    }
  },
}));
