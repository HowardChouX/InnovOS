import { create } from 'zustand';
import type { WorkflowState } from '../types/workflow';
import { workflowApi } from '../api/workflow';

export interface WorkflowStatus {
  currentPhase: string;
  currentLabel: string;
  progress: number;
  phaseStatus: Record<string, 'pending' | 'running' | 'completed' | 'failed'>;
  history: Array<{ from: string; event: string; to: string }>;
}

interface WorkflowStore {
  workflow: WorkflowState | null;
  loading: boolean;
  polling: boolean;
  currentPhase: string;
  phaseStatus: Record<string, 'pending' | 'running' | 'completed' | 'failed'>;
  isRunning: boolean;
  fetchWorkflow: (taskId: string) => Promise<void>;
  startPolling: (taskId: string) => void;
  stopPolling: () => void;
  reset: () => void;
  clearWorkflow: () => void;
}

let pollTimer: ReturnType<typeof setInterval> | null = null;

export const useWorkflowStore = create<WorkflowStore>((set, get) => ({
  workflow: null,
  loading: false,
  polling: false,
  currentPhase: 'demand_portrait',
  phaseStatus: {
    demand_portrait: 'pending',
    problem_modeling: 'pending',
    patent_search: 'pending',
    solution_gen: 'pending',
    evaluation: 'pending',
  },
  isRunning: false,
  fetchWorkflow: async (taskId) => {
    set({ loading: true });
    try {
      const workflow = await workflowApi.getByTaskId(taskId);
      set({ workflow, loading: false, isRunning: workflow.status === 'running' });
    } catch {
      set({ workflow: null, loading: false });
    }
  },
  startPolling: (taskId) => {
    get().stopPolling();
    set({ polling: true, isRunning: true });

    const poll = async () => {
      try {
        const workflow = await workflowApi.getByTaskId(taskId);
        set({ workflow, isRunning: workflow.status === 'running' });
        if (workflow.status === 'completed' || workflow.status === 'failed') {
          get().stopPolling();
        }
      } catch (err) {
        console.warn('Workflow poll warning (will retry):', err);
      }
    };

    poll();
    pollTimer = setInterval(poll, 1000);
  },
  stopPolling: () => {
    if (pollTimer) { clearInterval(pollTimer); pollTimer = null; }
    set({ polling: false, isRunning: false });
  },
  clearWorkflow: () => set({ workflow: null, isRunning: false }),
  reset: () => { get().stopPolling(); set({ workflow: null, isRunning: false }); },
}));
