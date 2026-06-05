import { create } from 'zustand';
import type { PatentStats } from '../types/patent';
import { patentsApi } from '../api/patents';

interface PatentStore {
  stats: PatentStats | null;
  loading: boolean;
  fetchStats: (taskId: string) => Promise<void>;
}

export const usePatentStore = create<PatentStore>((set) => ({
  stats: null,
  loading: false,
  fetchStats: async () => {
    set({ loading: true });
    try {
      const stats = await patentsApi.getStats();
      set({ stats, loading: false });
    } catch {
      set({ loading: false });
    }
  },
}));
