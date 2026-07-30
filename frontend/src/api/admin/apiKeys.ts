import { apiRequest } from '../client';

// API Key 数据类型(响应 — 不含 plaintext)
export interface ApiKeyMetadata {
  id: number;
  providerId: string;
  name: string;
  masked: string;
  prefix?: string | null;
  fingerprint: string;
  priority: number;
  isActive: boolean;
  maxRpm?: number | null;
  requestCount: number;
  successCount: number;
  failureCount: number;
  lastUsedAt?: string | null;
  cooldownUntil?: string | null;
  lastErrorCode?: string | null;
  createdBy?: number | null;
  updatedBy?: number | null;
}

// 创建 Key 请求
export interface CreateApiKeyInput {
  name: string;
  apiKey: string;
  priority?: number;
  maxRpm?: number | null;
}

// 更新 Key 元数据请求
export interface UpdateApiKeyInput {
  name?: string;
  priority?: number;
  maxRpm?: number | null;
  isActive?: boolean;
}

// 替换 Key 明文请求
export interface ReplaceApiKeyInput {
  apiKey: string;
}

export const apiKeysApi = {
  list: (providerId: string): Promise<{ data: ApiKeyMetadata[] }> =>
    apiRequest<{ data: ApiKeyMetadata[] }>(
      `/api/admin/providers/${encodeURIComponent(providerId)}/keys`,
    ),

  create: (
    providerId: string,
    input: CreateApiKeyInput,
  ): Promise<{ data: ApiKeyMetadata }> =>
    apiRequest(`/api/admin/providers/${encodeURIComponent(providerId)}/keys`, {
      method: 'POST',
      body: JSON.stringify(input),
    }),

  update: (
    providerId: string,
    keyId: number,
    input: UpdateApiKeyInput,
  ): Promise<{ data: ApiKeyMetadata }> =>
    apiRequest(
      `/api/admin/providers/${encodeURIComponent(providerId)}/keys/${keyId}`,
      { method: 'PATCH', body: JSON.stringify(input) },
    ),

  replaceSecret: (
    providerId: string,
    keyId: number,
    apiKey: string,
  ): Promise<{ data: ApiKeyMetadata }> =>
    apiRequest(
      `/api/admin/providers/${encodeURIComponent(providerId)}/keys/${keyId}/secret`,
      { method: 'PUT', body: JSON.stringify({ apiKey }) },
    ),

  activate: (
    providerId: string,
    keyId: number,
  ): Promise<{ data: ApiKeyMetadata }> =>
    apiRequest(
      `/api/admin/providers/${encodeURIComponent(providerId)}/keys/${keyId}/activate`,
      { method: 'POST' },
    ),

  deactivate: (
    providerId: string,
    keyId: number,
  ): Promise<{ data: ApiKeyMetadata }> =>
    apiRequest(
      `/api/admin/providers/${encodeURIComponent(providerId)}/keys/${keyId}/deactivate`,
      { method: 'POST' },
    ),

  delete: (providerId: string, keyId: number): Promise<{ message: string }> =>
    apiRequest(
      `/api/admin/providers/${encodeURIComponent(providerId)}/keys/${keyId}`,
      { method: 'DELETE' },
    ),
};