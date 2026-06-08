import { apiRequest } from '../client';

export interface Provider {
  id?: number;
  providerId: string;
  name: string;
  protocol: string;
  apiHost: string;
  hasApiKey: boolean;
  apiKeyMasked?: string;
  apiModel?: string;
  models: string[];
  isEnabled: boolean;
  priority?: number;
  maxRpm?: number;
  currentRpm?: number;
  requestCount?: number;
  createdAt?: string;
  isConfigured?: boolean;
  website?: string;
  keyUrl?: string;
  docsUrl?: string;
  category?: string;
}

export const providersApi = {
  listBuiltin: (): Promise<{ data: Provider[] }> =>
    apiRequest<{ data: Provider[] }>('/api/admin/providers/builtin'),

  list: (): Promise<{ data: Provider[] }> =>
    apiRequest<{ data: Provider[] }>('/api/admin/providers'),

  add: (data: {
    provider_id: string;
    name: string;
    protocol?: string;
    api_host: string;
    api_key?: string;
    api_model?: string;
    models?: string[];
    priority?: number;
    max_rpm?: number;
  }) => apiRequest('/api/admin/providers', {
    method: 'POST',
    body: JSON.stringify(data),
  }),

  update: (providerId: string, data: {
    name?: string;
    api_host?: string;
    api_key?: string;
    api_model?: string;
    models?: string[];
    is_enabled?: boolean;
    priority?: number;
    max_rpm?: number;
  }) => apiRequest(`/api/admin/providers/${providerId}`, {
    method: 'PUT',
    body: JSON.stringify(data),
  }),

  delete: (providerId: string) =>
    apiRequest(`/api/admin/providers/${providerId}`, { method: 'DELETE' }),

  check: (providerId: string, model?: string): Promise<{ data: { status: string; latency_ms?: number; message?: string; model?: string } }> =>
    apiRequest(`/api/admin/providers/${providerId}/check`, {
      method: 'POST',
      body: JSON.stringify(model ? { model } : {}),
    }),

  detectModels: (providerId: string, apiKey?: string): Promise<{ data: { models: string[] } }> =>
    apiRequest(`/api/admin/providers/${providerId}/detect-models`, {
      method: 'POST',
      body: JSON.stringify(apiKey ? { api_key: apiKey } : {}),
    }),
};
