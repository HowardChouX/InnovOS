import { apiRequest } from './client';

export interface MonitorOverview {
  totalTasks: number;
  completedTasks: number;
  failedTasks: number;
  successRate: number;
  totalAnalyses: number;
  totalSolutions: number;
  avgRating: number;
}

export interface TaskStats {
  byStatus: Record<string, number>;
  recent7days: { date: string; count: number }[];
}

export interface KeyUsage {
  id: number;
  name: string;
  requests: number;
  rpm: number;
  maxRpm: number;
  isActive: boolean;
}

export interface KeyStats {
  totalKeys: number;
  activeKeys: number;
  totalRequests: number;
  keyUsage: KeyUsage[];
}

export interface SystemStatus {
  uptime: string;
  version: string;
  pythonVersion: string;
  platform: string;
  dbSize: string;
  totalUsers: number;
  totalTasks: number;
  totalPatents: number;
  apiKeys: string;
  memory: {
    total: string;
    used: string;
    percent: number;
  };
  cpu: {
    cores: number;
    usage: number;
  };
  aiStats: {
    totalCalls: number;
    successCalls: number;
    failedCalls: number;
  };
}

export interface HealthCheck {
  status: 'healthy' | 'degraded';
  checks: {
    database: { status: string; responseMs?: number; message?: string };
    disk: { status: string; usedPercent?: number; freeGB?: number; message?: string };
    memory: { status: string; usedPercent?: number; availableGB?: number; message?: string };
    backend: { status: string; responseMs?: number; message?: string };
    aiApi: { status: string; responseMs?: number; message?: string };
  };
}

export const monitorApi = {
  async getOverview(): Promise<MonitorOverview> {
    const res = await apiRequest<{ data: MonitorOverview }>('/api/admin/monitor/overview');
    return res.data;
  },

  async getTaskStats(): Promise<TaskStats> {
    const res = await apiRequest<{ data: TaskStats }>('/api/admin/monitor/tasks');
    return res.data;
  },

  async getKeyStats(): Promise<KeyStats> {
    const res = await apiRequest<{ data: KeyStats }>('/api/admin/monitor/keys');
    return res.data;
  },

  async getSystemStatus(): Promise<SystemStatus> {
    const res = await apiRequest<{ data: SystemStatus }>('/api/admin/monitor/system');
    return res.data;
  },

  async getHealth(): Promise<HealthCheck> {
    const res = await apiRequest<HealthCheck>('/api/health');
    return res;
  },
};
