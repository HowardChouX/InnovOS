import { create } from 'zustand';
import {
  monitorApi,
  type MonitorOverview,
  type TaskStats,
  type KeyStats,
  type SystemStatus,
} from '../api/monitor';

interface MonitorStore {
  overview: MonitorOverview | null;
  taskStats: TaskStats | null;
  keyStats: KeyStats | null;
  systemStatus: SystemStatus | null;
  loading: boolean;
  fetchOverview: () => Promise<void>;
  fetchTaskStats: () => Promise<void>;
  fetchKeyStats: () => Promise<void>;
  fetchSystemStatus: () => Promise<void>;
  fetchAll: () => Promise<void>;
}

export const useMonitorStore = create<MonitorStore>((set) => ({
  overview: null,
  taskStats: null,
  keyStats: null,
  systemStatus: null,
  loading: false,

  fetchOverview: async () => {
    try {
      const overview = await monitorApi.getOverview();
      set({ overview });
    } catch {
      // silently fail
    }
  },

  fetchTaskStats: async () => {
    try {
      const taskStats = await monitorApi.getTaskStats();
      set({ taskStats });
    } catch {
      // silently fail
    }
  },

  fetchKeyStats: async () => {
    try {
      const keyStats = await monitorApi.getKeyStats();
      set({ keyStats });
    } catch {
      // silently fail
    }
  },

  fetchSystemStatus: async () => {
    try {
      const systemStatus = await monitorApi.getSystemStatus();
      set({ systemStatus });
    } catch {
      // silently fail
    }
  },

  fetchAll: async () => {
    set({ loading: true });
    try {
      const [overview, taskStats] = await Promise.all([
        monitorApi.getOverview(),
        monitorApi.getTaskStats(),
      ]);
      set({ overview, taskStats });
    } catch {
      // silently fail
    } finally {
      set({ loading: false });
    }
  },
}));
