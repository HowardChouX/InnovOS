import { create } from 'zustand';
import type { WorkflowState } from '../types/workflow';
import { workflowApi } from '../api/workflow';
import { analysisApi } from '../api/analysis';
import { useTaskStore } from './useTaskStore';

type PhaseStatus = 'pending' | 'running' | 'completed' | 'failed';

interface WorkflowStore {
  workflow: WorkflowState | null;
  loading: boolean;
  polling: boolean;
  phaseStatus: Record<string, PhaseStatus>;
  currentPhase: string;
  isRunning: boolean;
  error: string | null;

  fetchWorkflow: (taskId: string) => Promise<void>;
  startPolling: (taskId: string) => void;
  stopPolling: () => void;
  clearWorkflow: () => void;
  cancelAnalysis: () => Promise<void>;
}

// ══════════════════════════════════════════════════════════
//  内部状态（非响应式）
// ══════════════════════════════════════════════════════════

let pollTimer: ReturnType<typeof setTimeout> | null = null;
let pollingTaskId: string | null = null;
let pollingFlag = false;
let pollStartTime = 0;

// 10 分钟最大轮询时长，避免无限轮询
const MAX_POLL_MS = 10 * 60 * 1000;

const AGENT_TO_PHASE: Record<string, string> = {
  agent1: 'demand_analysis',
  agent2: 'problem_definition',
  agent5: 'patent_search',
  agent3: 'solution_gen',
  agent4: 'evaluation',
  // agent6 (conversion) 后端仍运行，但前端不再显示为独立阶段
  // 其完成触发 video_display mock 自动完成
};

const PHASE_ORDER = [
  'demand_analysis',
  'problem_definition',
  'patent_search',
  'solution_gen',
  'evaluation',
  'video_display',
] as const;

const DEFAULT_PHASE_STATUS: Record<string, PhaseStatus> = {
  demand_analysis: 'pending',
  problem_definition: 'pending',
  patent_search: 'pending',
  solution_gen: 'pending',
  evaluation: 'pending',
  video_display: 'pending',
};

// ══════════════════════════════════════════════════════════
//  纯函数：从 workflow.steps 派生 phaseStatus / currentPhase
// ══════════════════════════════════════════════════════════

function syncPhaseStatus(steps: { agentId?: string; agent_id?: string; status: string }[]) {
  const status = { ...DEFAULT_PHASE_STATUS };
  let conversionDone = false;
  for (const step of steps) {
    const agentId = step.agentId || step.agent_id;
    const phase = AGENT_TO_PHASE[agentId || ''];
    if (phase) {
      status[phase] = step.status as PhaseStatus;
    }
    // agent6 (conversion) 完成后触发 video_display mock
    if (agentId === 'agent6' && step.status === 'completed') {
      conversionDone = true;
    }
  }
  // Mock: video_display 阶段无后端 agent，conversion(agent6) 完成后自动标记完成
  if (conversionDone) {
    status.video_display = 'completed';
  }
  return status;
}

function determineCurrentPhase(phaseStatus: Record<string, PhaseStatus>): string {
  // 1. 有 running → 显示它
  for (const phase of PHASE_ORDER) {
    if (phaseStatus[phase] === 'running') return phase;
  }
  // 2. 有 failed → 显示它
  for (const phase of PHASE_ORDER) {
    if (phaseStatus[phase] === 'failed') return phase;
  }
  // 3. 有 pending → 显示它（等待后端启动）
  for (const phase of PHASE_ORDER) {
    if (phaseStatus[phase] === 'pending') return phase;
  }
  // 4. 全部 completed → 显示最后一个
  for (let i = PHASE_ORDER.length - 1; i >= 0; i--) {
    if (phaseStatus[PHASE_ORDER[i]] === 'completed') return PHASE_ORDER[i];
  }
  return 'demand_analysis';
}

// ══════════════════════════════════════════════════════════
//  Store
// ══════════════════════════════════════════════════════════

export const useWorkflowStore = create<WorkflowStore>((set, get) => ({
  workflow: null,
  loading: false,
  polling: false,
  phaseStatus: { ...DEFAULT_PHASE_STATUS },
currentPhase: 'demand_analysis',
    isRunning: false,
  error: null,

  cancelAnalysis: async () => {
    const taskId = useTaskStore.getState().selectedTaskId;
    if (!taskId) return;
    try {
      await analysisApi.cancel(taskId);
    } catch (e) {
      console.error('[useWorkflowStore] cancelAnalysis failed:', e);
    }
    get().stopPolling();
    get().clearWorkflow();
    useTaskStore.getState().fetchTasks();
  },

  fetchWorkflow: async (taskId) => {
    set({ loading: true, error: null });
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
      // 如果 workflow 正在运行，自动启动轮询（proceed 后重新追踪）
      if (workflow.status === 'running') {
        get().startPolling(taskId);
      }
    } catch (e) {
      console.error('[useWorkflowStore] fetchWorkflow failed:', e);
      set({ workflow: null, loading: false, error: '加载工作流失败' });
    }
  },

  startPolling: (taskId) => {
    // 同一任务已在轮询 → 跳过
    if (pollingTaskId === taskId && pollingFlag) return;

    // 切换任务 → 先停掉旧的
    if (pollingTaskId !== taskId) {
      get().stopPolling();
    }

    pollingTaskId = taskId;
    pollStartTime = Date.now();
    set({ isRunning: true, polling: true });

    const poll = async () => {
      if (pollingTaskId !== taskId) return; // 任务已切换，退出
      if (pollingFlag) return;
      pollingFlag = true;

      // 超时保护
      if (Date.now() - pollStartTime > MAX_POLL_MS) {
        console.warn('[useWorkflowStore] 轮询超时，自动停止');
        set({ error: '分析超时，请检查后端服务或稍后重试' });
        get().stopPolling();
        return;
      }

      try {
        const workflow = await workflowApi.getByTaskId(taskId);
        if (pollingTaskId !== taskId) return; // 期间任务切换了

        const phaseStatus = syncPhaseStatus(workflow.steps);
        const currentPhase = determineCurrentPhase(phaseStatus);
        const isRunning = workflow.status === 'running';
        set({ workflow, phaseStatus, currentPhase, isRunning, error: null });

        // 非运行状态（awaiting_rating / completed / failed）→ 停止轮询，结果已就绪
        if (workflow.status !== 'running') {
          get().stopPolling();
          // 刷新任务列表状态
          useTaskStore.getState().fetchTasks();
          return;
        }
      } catch (err) {
        console.warn('[useWorkflowStore] poll warning:', err);
        // 不设置 error，让下一轮重试
      } finally {
        pollingFlag = false;
        if (pollingTaskId === taskId) {
          pollTimer = setTimeout(poll, 2000);
        }
      }
    };

    poll();
  },

  stopPolling: () => {
    if (pollTimer !== null) {
      clearTimeout(pollTimer);
      pollTimer = null;
    }
    pollingTaskId = null;
    pollingFlag = false;
    set({ isRunning: false, polling: false });
  },

  clearWorkflow: () => {
    get().stopPolling();
    set({
      workflow: null,
      isRunning: false,
      phaseStatus: { ...DEFAULT_PHASE_STATUS },
      currentPhase: 'demand_analysis',
      error: null,
    });
  },
}));
