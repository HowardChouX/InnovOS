import { apiRequest } from '../client';

export type ProviderHealth = 'healthy' | 'degraded' | 'unhealthy';

export interface Provider {
  providerId: string;
  name: string;
  notes: string;
  apiHost: string;
  apiModel: string;
  isEnabled: boolean;
  health?: ProviderHealth;
  createdAt?: string;
  updatedAt?: string;
}

export interface AddProviderInput {
  provider_id: string;
  name: string;
  notes?: string;
  api_host: string;
  api_key: string;
  api_model?: string;
}

export interface UpdateProviderInput {
  name?: string;
  notes?: string;
  api_host?: string;
  api_key?: string;
  api_model?: string;
  is_enabled?: boolean;
}

export const providersApi = {
  list: (): Promise<{ data: Provider[] }> =>
    apiRequest<{ data: Provider[] }>('/api/admin/providers'),

  add: (data: AddProviderInput): Promise<{ data: Provider }> =>
    apiRequest<{ data: Provider }>('/api/admin/providers', {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  update: (providerId: string, data: UpdateProviderInput): Promise<{ data: Provider }> =>
    apiRequest<{ data: Provider }>(`/api/admin/providers/${encodeURIComponent(providerId)}`, {
      method: 'PUT',
      body: JSON.stringify(data),
    }),

  delete: (providerId: string): Promise<{ message: string }> =>
    apiRequest<{ message: string }>(`/api/admin/providers/${encodeURIComponent(providerId)}`, {
      method: 'DELETE',
    }),

  detect: (
    apiHost: string,
    apiKey: string,
  ): Promise<{ data: { models: Array<{ id: string; name: string }> } }> =>
    apiRequest<{ data: { models: Array<{ id: string; name: string }> } }>(
      '/api/admin/providers/detect',
      {
        method: 'POST',
        body: JSON.stringify({ api_host: apiHost, api_key: apiKey }),
      },
    ),

  detectModels: (
    providerId: string,
  ): Promise<{ data: { models: Array<{ id: string; name: string }> } }> =>
    apiRequest<{ data: { models: Array<{ id: string; name: string }> } }>(
      `/api/admin/providers/${encodeURIComponent(providerId)}/detect-models`,
      { method: 'POST' },
    ),

  check: (
    providerId: string,
    model?: string,
  ): Promise<{
    data: {
      status: 'ok' | 'error' | 'not_found' | 'no_key' | 'no_model';
      status_code?: number;
      latency_ms?: number;
      model?: string;
      message?: string;
    };
  }> =>
    apiRequest(`/api/admin/providers/${encodeURIComponent(providerId)}/check`, {
      method: 'POST',
      body: JSON.stringify(model ? { model } : {}),
    }),
};
