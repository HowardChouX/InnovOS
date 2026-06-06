import { create } from 'zustand';
import type { ConflictAnalysis } from '../types/analysis';
import { analysisApi } from '../api/analysis';

interface AnalysisStore {
  analysis: ConflictAnalysis | null;
  loading: boolean;
  analyzing: boolean;
  fetchAnalysis: (taskId: string) => Promise<void>;
  triggerAnalysis: (taskId: string) => Promise<void>;
}

export const useAnalysisStore = create<AnalysisStore>((set) => ({
  analysis: null,
  loading: false,
  analyzing: false,

  fetchAnalysis: async (taskId) => {
    set({ loading: true });
    try {
      const analysis = await analysisApi.getByTaskId(taskId);
      set({ analysis, loading: false });
    } catch {
      set({ loading: false });
    }
  },

  triggerAnalysis: async (taskId) => {
    set({ analyzing: true, loading: true });
    try {
      await analysisApi.triggerAnalysis(taskId);
      // 分析已启动，不设置 analysis，等待后台完成
      // 完成后通过 fetchAnalysis 获取结果
      set({ analyzing: false, loading: false });
    } catch {
      set({ analyzing: false, loading: false });
    }
  },
}));
