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
  clearWorkflow: () => void;
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
      // 关键：失败时清除旧workflow数据，避免显示错误task的workflow
      set({ workflow: null, loading: false });
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
        // 如果workflow还没创建（404），继续轮询而不是停止
        // 其他错误也继续轮询，让后续重试恢复
        console.warn('Workflow poll warning (will retry):', err);
      }
    };

    poll();
    pollTimer = setInterval(poll, 1000);
  },
  stopPolling: () => {
    if (pollTimer) {
      clearInterval(pollTimer);
      pollTimer = null;
    }
    set({ polling: false });
  },
  clearWorkflow: () => {
    set({ workflow: null });
  },
  reset: () => {
    get().stopPolling();
    set({ workflow: null });
  },
}));
