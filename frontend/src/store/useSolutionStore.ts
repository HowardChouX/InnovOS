import { create } from 'zustand';
import type { Solution } from '../types/solution';
import { solutionsApi } from '../api/solutions';

interface SolutionStore {
  solutions: Solution[];
  selectedSolution: Solution | null;
  loading: boolean;
  error: string | null;
  fetchSolutions: (taskId: string) => Promise<void>;
  selectSolution: (solution: Solution | null) => void;
  updateRating: (taskId: string, solutionId: string, rating: number) => Promise<void>;
}

export const useSolutionStore = create<SolutionStore>((set) => ({
  solutions: [],
  selectedSolution: null,
  loading: false,
  error: null,
  fetchSolutions: async (taskId) => {
    set({ loading: true });
    try {
      const solutions = await solutionsApi.getByTaskId(taskId);
      set({ solutions, loading: false });
    } catch (e) {
      console.error('[useSolutionStore] fetchSolutions failed:', e);
      set({ loading: false, error: e instanceof Error ? e.message : '获取方案列表失败' });
    }
  },
  selectSolution: (solution) => set({ selectedSolution: solution }),
  updateRating: async (taskId, solutionId, rating) => {
    try {
      const updated = await solutionsApi.updateRating(taskId, solutionId, rating);
      set((s) => ({
        solutions: s.solutions.map((sol) => (sol.id === solutionId ? updated : sol)),
        selectedSolution: s.selectedSolution?.id === solutionId ? updated : s.selectedSolution,
      }));
    } catch (e) {
      console.error('[useSolutionStore] updateRating failed:', e);
    }
  },
}));
