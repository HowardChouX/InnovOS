import { create } from 'zustand';
import type { PatentStats } from '../types/patent';
import { patentsApi } from '../api/patents';

interface PatentStore {
  stats: PatentStats | null;
  loading: boolean;
  error: string | null;
  fetchStats: () => Promise<void>;
}

export const usePatentStore = create<PatentStore>((set) => ({
  stats: null,
  loading: false,
  error: null,
  fetchStats: async () => {
    set({ loading: true });
    try {
      const stats = await patentsApi.getStats();
      set({ stats, loading: false });
    } catch (e) {
      console.error('[usePatentStore] fetchStats failed:', e);
      set({ loading: false, error: e instanceof Error ? e.message : '获取专利统计失败' });
    }
  },
}));
