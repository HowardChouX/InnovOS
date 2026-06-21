import { create } from 'zustand';
import type { Evaluation, EvaluationSummary } from '../types/evaluation';
import { evaluationApi } from '../api/evaluation';

interface EvaluationStore {
  evaluation: Evaluation | null;
  history: EvaluationSummary[];
  loading: boolean;
  error: string | null;
  evaluate: (solutionId: string) => Promise<void>;
  fetchHistory: (solutionId: string) => Promise<void>;
}

export const useEvaluationStore = create<EvaluationStore>((set) => ({
  evaluation: null,
  history: [],
  loading: false,
  error: null,
  evaluate: async (solutionId) => {
    set({ loading: true });
    try {
      const evaluation = await evaluationApi.evaluate(solutionId);
      set({ evaluation, loading: false });
    } catch (e) {
      console.error('[useEvaluationStore] evaluate failed:', e);
      set({ loading: false, error: e instanceof Error ? e.message : '评估失败' });
    }
  },
  fetchHistory: async (solutionId) => {
    set({ loading: true });
    try {
      const history = await evaluationApi.getHistory(solutionId);
      set({ history, loading: false });
    } catch (e) {
      console.error('[useEvaluationStore] fetchHistory failed:', e);
      set({ loading: false, error: e instanceof Error ? e.message : '获取评估历史失败' });
    }
  },
}));
