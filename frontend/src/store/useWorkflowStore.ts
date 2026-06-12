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

// 后端 agent_id 到前端 phaseId 的映射
const AGENT_TO_PHASE: Record<string, string> = {
  agent1: 'demand_portrait',
  agent2: 'problem_modeling',
  agent5: 'patent_search',
  agent3: 'solution_gen',
  agent4: 'evaluation',
};

// 默认 phaseStatus
const DEFAULT_PHASE_STATUS: Record<string, 'pending' | 'running' | 'completed' | 'failed'> = {
  demand_portrait: 'pending',
  problem_modeling: 'pending',
  patent_search: 'pending',
  solution_gen: 'pending',
  evaluation: 'pending',
};

/** 从 workflow.steps 同步 phaseStatus */
function syncPhaseStatus(steps: { agentId: string; status: string }[]): Record<string, 'pending' | 'running' | 'completed' | 'failed'> {
  const status = { ...DEFAULT_PHASE_STATUS };
  for (const step of steps) {
    const phase = AGENT_TO_PHASE[step.agentId];
    if (phase) {
      (status as any)[phase] = step.status;
    }
  }
  return status;
}

/** 确定当前阶段：找到第一个 running 或 pending 的阶段 */
function determineCurrentPhase(phaseStatus: Record<string, string>): string {
  const order = ['demand_portrait', 'problem_modeling', 'patent_search', 'solution_gen', 'evaluation'];
  for (const phase of order) {
    if (phaseStatus[phase] === 'running' || phaseStatus[phase] === 'pending') {
      return phase;
    }
  }
  return 'completed';
}

export const useWorkflowStore = create<WorkflowStore>((set, get) => ({
  workflow: null,
  loading: false,
  polling: false,
  currentPhase: 'demand_portrait',
  phaseStatus: { ...DEFAULT_PHASE_STATUS },
  isRunning: false,
  fetchWorkflow: async (taskId) => {
    set({ loading: true });
    try {
      const workflow = await workflowApi.getByTaskId(taskId);
      const phaseStatus = syncPhaseStatus(workflow.steps);
      const currentPhase = determineCurrentPhase(phaseStatus);
      set({
        workflow,
        phaseStatus,
        currentPhase,
        loading: false,
        isRunning: workflow.status === 'running',
      });
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
        const phaseStatus = syncPhaseStatus(workflow.steps);
        const currentPhase = determineCurrentPhase(phaseStatus);
        const isRunning = workflow.status === 'running';
        set({ workflow, phaseStatus, currentPhase, isRunning });
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
  clearWorkflow: () => set({ workflow: null, isRunning: false, phaseStatus: { ...DEFAULT_PHASE_STATUS }, currentPhase: 'demand_portrait' }),
  reset: () => { get().stopPolling(); set({ workflow: null, isRunning: false, phaseStatus: { ...DEFAULT_PHASE_STATUS }, currentPhase: 'demand_portrait' }); },
}));
