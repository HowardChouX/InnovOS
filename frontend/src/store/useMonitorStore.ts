import { create } from 'zustand';
import {
  monitorApi,
  type MonitorOverview,
  type TaskStats,
  type KeyStats,
  type SystemStatus,
  type HealthCheck,
} from '../api/monitor';

interface MonitorStore {
  overview: MonitorOverview | null;
  taskStats: TaskStats | null;
  keyStats: KeyStats | null;
  systemStatus: SystemStatus | null;
  health: HealthCheck | null;
  loading: boolean;
  error: string | null;
  fetchOverview: () => Promise<void>;
  fetchTaskStats: () => Promise<void>;
  fetchKeyStats: () => Promise<void>;
  fetchSystemStatus: () => Promise<void>;
  fetchHealth: () => Promise<void>;
  fetchAll: () => Promise<void>;
}

export const useMonitorStore = create<MonitorStore>((set) => ({
  overview: null,
  taskStats: null,
  keyStats: null,
  systemStatus: null,
  health: null,
  loading: false,
  error: null,

  fetchOverview: async () => {
    try {
      const overview = await monitorApi.getOverview();
      set({ overview, error: null });
    } catch (e) {
      set({ error: e instanceof Error ? e.message : '加载概览数据失败' });
    }
  },

  fetchTaskStats: async () => {
    try {
      const taskStats = await monitorApi.getTaskStats();
      set({ taskStats, error: null });
    } catch (e) {
      set({ error: e instanceof Error ? e.message : '加载任务统计失败' });
    }
  },

  fetchKeyStats: async () => {
    try {
      const keyStats = await monitorApi.getKeyStats();
      set({ keyStats, error: null });
    } catch (e) {
      set({ error: e instanceof Error ? e.message : '加载 Key 统计失败' });
    }
  },

  fetchSystemStatus: async () => {
    try {
      const systemStatus = await monitorApi.getSystemStatus();
      set({ systemStatus, error: null });
    } catch (e) {
      set({ error: e instanceof Error ? e.message : '加载系统状态失败' });
    }
  },

  fetchHealth: async () => {
    try {
      const health = await monitorApi.getHealth();
      set({ health, error: null });
    } catch (e) {
      set({ error: e instanceof Error ? e.message : '加载健康检查失败' });
    }
  },

  fetchAll: async () => {
    set({ loading: true, error: null });
    try {
      const [overview, taskStats] = await Promise.all([
        monitorApi.getOverview(),
        monitorApi.getTaskStats(),
      ]);
      set({ overview, taskStats });
    } catch (e) {
      set({ error: e instanceof Error ? e.message : '加载监控数据失败' });
    } finally {
      set({ loading: false });
    }
  },
}));
