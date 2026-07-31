import { apiRequest } from '../client';

export interface UserModelService {
  provider_id: string;
  name: string;
  api_host: string;
  api_model: string;
  failover_order: number;
  is_enabled: boolean;
  is_healthy?: boolean;
  consecutive_failures?: number;
  cooldown_until?: string | null;
}

export interface AvailableModelService {
  provider_id: string;
  name: string;
  api_host: string;
  api_model: string;
  already_enabled: boolean;
  is_healthy?: boolean;
}

export const userModelServicesApi = {
  list: (userId: number): Promise<{ data: UserModelService[] }> =>
    apiRequest<{ data: UserModelService[] }>(`/api/admin/users/${userId}/model-services`),

  listAvailable: (userId: number): Promise<{ data: AvailableModelService[] }> =>
    apiRequest<{ data: AvailableModelService[] }>(
      `/api/admin/users/${userId}/model-services/available`,
    ),

  add: (userId: number, providerId: string): Promise<{ data: UserModelService[] }> =>
    apiRequest(`/api/admin/users/${userId}/model-services`, {
      method: 'POST',
      body: JSON.stringify({ provider_id: providerId }),
    }),

  remove: (userId: number, providerId: string): Promise<void> =>
    apiRequest<void>(
      `/api/admin/users/${userId}/model-services/${encodeURIComponent(providerId)}`,
      { method: 'DELETE' },
    ),

  toggle: (
    userId: number,
    providerId: string,
    isEnabled: boolean,
  ): Promise<{ data: { is_enabled: boolean } }> =>
    apiRequest(
      `/api/admin/users/${userId}/model-services/${encodeURIComponent(providerId)}/toggle`,
      {
        method: 'POST',
        body: JSON.stringify({ is_enabled: isEnabled }),
      },
    ),

  reorder: (userId: number, providerIds: string[]): Promise<{ data: UserModelService[] }> =>
    apiRequest(`/api/admin/users/${userId}/model-services/order`, {
      method: 'PUT',
      body: JSON.stringify({ provider_ids: providerIds }),
    }),
};
