import { apiRequest } from '../client';

export type UsageRange = '1d' | '7d' | '30d' | '90d';

export interface UsageSummary {
  total_requests: number;
  total_tokens: number;
  avg_latency_ms: number;
  success_rate: number;
  range: UsageRange;
}

export interface ProviderUsage {
  provider_id: string;
  requests: number;
  total_tokens: number;
  avg_latency_ms: number;
  success_rate: number;
}

export interface ModelUsage {
  model_id: string;
  requests: number;
  input_tokens: number;
  output_tokens: number;
  total_tokens: number;
  avg_latency_ms: number;
  success_rate: number;
}

export interface CallLogRow {
  id: number;
  user_id: number | null;
  provider_id: string;
  model_id: string;
  purpose: string;
  input_tokens: number;
  output_tokens: number;
  total_tokens: number;
  latency_ms: number;
  status_code: number;
  is_success: boolean;
  error_category: string | null;
  error_message: string | null;
  is_streaming: boolean;
  failover_from_provider: string | null;
  failover_attempt: number;
  created_at: string;
}

function qs(params: Record<string, string | number | undefined>): string {
  const usp = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) {
    if (v !== undefined && v !== null) usp.set(k, String(v));
  }
  const s = usp.toString();
  return s ? `?${s}` : '';
}

export const usageApi = {
  summary: (range: UsageRange = '7d', userId?: number): Promise<{ data: UsageSummary }> =>
    apiRequest<{ data: UsageSummary }>(`/api/admin/usage/summary${qs({ range, user_id: userId })}`),

  byProvider: (range: UsageRange = '7d', userId?: number): Promise<{ data: ProviderUsage[] }> =>
    apiRequest<{ data: ProviderUsage[] }>(
      `/api/admin/usage/by-provider${qs({ range, user_id: userId })}`,
    ),

  byModel: (range: UsageRange = '7d', userId?: number): Promise<{ data: ModelUsage[] }> =>
    apiRequest<{ data: ModelUsage[] }>(
      `/api/admin/usage/by-model${qs({ range, user_id: userId })}`,
    ),

  recent: (limit: number = 50, userId?: number): Promise<{ data: CallLogRow[] }> =>
    apiRequest<{ data: CallLogRow[] }>(`/api/admin/usage/recent${qs({ limit, user_id: userId })}`),
};
