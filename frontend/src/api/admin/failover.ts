import { apiRequest } from '../client';

export interface ProviderHealthRow {
  provider_id: string;
  name: string;
  is_healthy: boolean;
  consecutive_failures: number;
  last_success_at: string | null;
  last_failure_at: string | null;
  cooldown_until: string | null;
  last_error_code: string | null;
}

export const failoverApi = {
  health: (): Promise<{ data: ProviderHealthRow[] }> =>
    apiRequest<{ data: ProviderHealthRow[] }>('/api/admin/failover/health'),

  reset: (providerId: string): Promise<{ data: { provider_id: string; is_healthy: boolean } }> =>
    apiRequest(`/api/admin/failover/${encodeURIComponent(providerId)}/reset`, { method: 'POST' }),
};
