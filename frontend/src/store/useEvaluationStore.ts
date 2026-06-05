import { create } from 'zustand';
import type { Evaluation, EvaluationSummary } from '../types/evaluation';
import { evaluationApi } from '../api/evaluation';

interface EvaluationStore {
  evaluation: Evaluation | null;
  history: EvaluationSummary[];
  loading: boolean;
  evaluate: (solutionId: string) => Promise<void>;
  fetchHistory: (solutionId: string) => Promise<void>;
}

export const useEvaluationStore = create<EvaluationStore>((set) => ({
  evaluation: null,
  history: [],
  loading: false,
  evaluate: async (solutionId) => {
    set({ loading: true });
    try {
      const evaluation = await evaluationApi.evaluate(solutionId);
      set({ evaluation, loading: false });
    } catch {
      set({ loading: false });
    }
  },
  fetchHistory: async (solutionId) => {
    set({ loading: true });
    try {
      const history = await evaluationApi.getHistory(solutionId);
      set({ history, loading: false });
    } catch {
      set({ loading: false });
    }
  },
}));
