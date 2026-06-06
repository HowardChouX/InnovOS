import { apiRequest } from './client';

export interface ApiKey {
  id: number;
  keyName: string;
  apiKey: string;
  apiBaseUrl: string;
  apiModel: string;
  isActive: boolean;
  priority: number;
  maxRpm: number;
  currentRpm: number;
  requestCount: number;
  lastUsedAt: string | null;
  createdAt: string;
}

export const keysApi = {
  async list(): Promise<ApiKey[]> {
    const res = await apiRequest<{ data: ApiKey[] }>('/api/keys');
    return res.data;
  },

  async create(input: {
    keyName: string;
    apiKey: string;
    apiBaseUrl: string;
    apiModel: string;
    priority?: number;
    maxRpm?: number;
  }): Promise<ApiKey> {
    const res = await apiRequest<{ data: ApiKey }>('/api/keys', {
      method: 'POST',
      body: JSON.stringify(input),
    });
    return res.data;
  },

  async update(id: number, input: Partial<ApiKey>): Promise<ApiKey> {
    const res = await apiRequest<{ data: ApiKey }>(`/api/keys/${id}`, {
      method: 'PUT',
      body: JSON.stringify(input),
    });
    return res.data;
  },

  async delete(id: number): Promise<void> {
    await apiRequest(`/api/keys/${id}`, { method: 'DELETE' });
  },

  async test(id: number): Promise<{ message: string; response?: string }> {
    const res = await apiRequest<{ message: string; response?: string }>(
      `/api/keys/${id}/test`,
      { method: 'POST' }
    );
    return res;
  },
};
