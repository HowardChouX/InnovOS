import { create } from 'zustand';
import type { ProblemModeling } from '../types/modeling';
import { modelingApi } from '../api/modeling';

export type ModelingStep = 'agent1' | 'agent2' | 'agent3' | 'agent4' | 'agent5' | 'agent6';

interface ModelingStore {
  modeling: ProblemModeling | null;
  loading: boolean;
  error: string | null;
  
  // 各步骤数据
  stepData: Partial<Record<ModelingStep, {
    status: 'pending' | 'running' | 'completed' | 'failed';
    data: any;
    timestamp: number;
  }>>;
  
  fetchModeling: (taskId: string) => Promise<void>;
  refreshModeling: (taskId: string) => Promise<void>;
  setModeling: (modeling: ProblemModeling | null) => void;
  updateStepData: (step: ModelingStep, data: any) => void;
  clearModeling: () => void;
}

export const useModelingStore = create<ModelingStore>((set) => ({
  modeling: null,
  loading: false,
  error: null,
  stepData: {},
  
  fetchModeling: async (taskId: string) => {
    set({ loading: true, error: null });
    try {
      const modeling = await modelingApi.getByTaskId(taskId);
      set({ modeling, loading: false });
    } catch (err: any) {
      // 404 表示尚未生成，不是错误
      if (err?.response?.status === 404) {
        set({ modeling: null, loading: false });
      } else {
        set({ error: err?.message || '获取问题建模失败', loading: false });
      }
    }
  },
  
  refreshModeling: async (taskId: string) => {
    try {
      const modeling = await modelingApi.getByTaskId(taskId);
      set({ modeling });
    } catch (err: any) {
      if (err?.response?.status !== 404) {
        set({ error: err?.message || '刷新问题建模失败' });
      }
    }
  },
  
  setModeling: (modeling: ProblemModeling | null) => {
    set({ modeling });
  },
  
  updateStepData: (step: ModelingStep, data: any) => {
    set((state) => ({
      stepData: {
        ...state.stepData,
        [step]: {
          status: 'completed',
          data,
          timestamp: Date.now(),
        },
      },
    }));
  },
  
  clearModeling: () => {
    set({ modeling: null, stepData: {}, error: null });
  },
}));