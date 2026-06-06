import { apiRequest } from './client';

export interface SidebarStats {
  todayTasks: number;
  completedTasks: number;
  analyzingTasks: number;
  patentCount: number;
}

export const sidebarApi = {
  async getStats(): Promise<SidebarStats> {
    const res = await apiRequest<{ data: SidebarStats }>('/api/sidebar/stats');
    return res.data;
  },
};
