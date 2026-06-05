import { create } from 'zustand';
import type { ConflictAnalysis } from '../types/analysis';
import { analysisApi } from '../api/analysis';

interface AnalysisStore {
  analysis: ConflictAnalysis | null;
  loading: boolean;
  fetchAnalysis: (taskId: string) => Promise<void>;
}

export const useAnalysisStore = create<AnalysisStore>((set) => ({
  analysis: null,
  loading: false,
  fetchAnalysis: async (taskId) => {
    set({ loading: true });
    try {
      const analysis = await analysisApi.getByTaskId(taskId);
      set({ analysis, loading: false });
    } catch {
      set({ loading: false });
    }
  },
}));
