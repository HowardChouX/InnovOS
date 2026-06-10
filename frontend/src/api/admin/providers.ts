import { apiRequest } from '../client';

// 模型条目：兼容旧格式字符串和新格式对象（含 capabilities）
export type ModelEntry = string | {
  id: string;
  capabilities?: string[];
  name?: string;
  label?: string;
  providerId?: string;
  modelId?: string;
  contextWindow?: number;
  maxOutputTokens?: number;
  endpointTypes?: string[];
  pricing?: Record<string, number>;
  isEnabled?: boolean;
  group?: string;
};

/** 从 ModelEntry 中提取模型 ID */
export function getModelId(m: ModelEntry): string {
  return typeof m === 'string' ? m : m.id;
}

export interface Provider {
  id?: number;
  providerId: string;
  name: string;
  protocol: string;
  apiHost: string;
  hasApiKey: boolean;
  apiKeyMasked?: string;
  apiModel?: string;
  models: ModelEntry[];
  isEnabled: boolean;
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
    models?: ModelEntry[];
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
    models?: ModelEntry[];
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

  detectModels: (providerId: string, apiKey?: string): Promise<{ data: { models: ModelEntry[] } }> =>
    apiRequest(`/api/admin/providers/${providerId}/detect-models`, {
      method: 'POST',
      body: JSON.stringify(apiKey ? { api_key: apiKey } : {}),
    }),

  listModels: (providerId: string): Promise<{ data: any[] }> =>
    apiRequest(`/api/admin/providers/${providerId}/models`),

  updateModel: (providerId: string, modelId: string, data: {
    is_enabled?: boolean;
    name?: string;
    group?: string;
    endpoint_types?: string[];
    capabilities?: string[];
    context_window?: number;
    max_output_tokens?: number;
  }): Promise<{ data: any }> =>
    apiRequest(`/api/admin/providers/${providerId}/models/${encodeURIComponent(modelId)}`, {
      method: 'PUT',
      body: JSON.stringify(data),
    }),

  deleteModel: (providerId: string, modelId: string): Promise<void> =>
    apiRequest(`/api/admin/providers/${providerId}/models/${encodeURIComponent(modelId)}`, {
      method: 'DELETE',
    }),

  /** 批量健康检查 — 并行测试多个模型连接，返回每个模型的状态/延迟/错误 */
  batchCheckModels: (providerId: string, models: string[]): Promise<{
    data: { providerId: string; models: Array<{ modelId: string; status: string; latency?: number; error?: string | null }> }
  }> =>
    apiRequest(`/api/admin/providers/${providerId}/models/check`, {
      method: 'POST',
      body: JSON.stringify({ models }),
    }),
};
