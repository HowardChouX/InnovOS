import { create } from 'zustand';
import type { ConflictAnalysis } from '../types/analysis';
import { analysisApi } from '../api/analysis';

interface AnalysisStore {
  analysis: ConflictAnalysis | null;
  loading: boolean;
  analyzing: boolean;
  error: string | null;
  fetchAnalysis: (taskId: string) => Promise<void>;
  triggerAnalysis: (taskId: string, knowledgeBaseIds?: string[]) => Promise<void>;
}

export const useAnalysisStore = create<AnalysisStore>((set) => ({
  analysis: null,
  loading: false,
  analyzing: false,
  error: null,

  fetchAnalysis: async (taskId) => {
    set({ loading: true });
    try {
      const analysis = await analysisApi.getByTaskId(taskId);
      set({ analysis, loading: false });
    } catch (e) {
      console.error('[useAnalysisStore] fetchAnalysis failed:', e);
      set({ loading: false, error: e instanceof Error ? e.message : '获取分析结果失败' });
    }
  },

  triggerAnalysis: async (taskId, knowledgeBaseIds) => {
    set({ analyzing: true, loading: true });
    try {
      await analysisApi.triggerAnalysis(taskId, knowledgeBaseIds);
      // 分析已启动，不设置 analysis，等待后台完成
      // 完成后通过 fetchAnalysis 获取结果
      set({ analyzing: false, loading: false });
    } catch (e) {
      console.error('[useAnalysisStore] triggerAnalysis failed:', e);
      set({ analyzing: false, loading: false, error: e instanceof Error ? e.message : '触发分析失败' });
    }
  },
}));
