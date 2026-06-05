import type { Patent, PatentStats } from '../types/patent';
import { apiRequest } from './client';

export const patentsApi = {
  async search(query: { q?: string }): Promise<{ data: Patent[]; total: number }> {
    const q = query.q ?? '';
    const res = await apiRequest<{ data: Patent[]; total: number }>(`/api/patents/search?q=${encodeURIComponent(q)}`);
    return res;
  },

  async getStats(): Promise<PatentStats> {
    const res = await apiRequest<{ data: PatentStats }>('/api/patents/stats');
    return res.data;
  },
};
