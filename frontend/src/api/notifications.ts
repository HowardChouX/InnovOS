import { apiRequest } from './client';

export interface Notification {
  id: number;
  userId: number;
  title: string;
  content: string;
  type: string;
  isRead: boolean;
  isRecalled: boolean;
  createdAt: string;
}

export interface CreateNotificationInput {
  user_id: number;
  title: string;
  content: string;
  type?: string;
}

export interface BatchNotificationInput {
  title: string;
  content: string;
  type?: string;
  user_ids?: number[];
}

export const notificationsApi = {
  async list(params?: { page?: number; pageSize?: number; unreadOnly?: boolean }): Promise<{ data: Notification[]; total: number }> {
    const searchParams = new URLSearchParams();
    if (params?.page) searchParams.set('page', String(params.page));
    if (params?.pageSize) searchParams.set('page_size', String(params.pageSize));
    if (params?.unreadOnly) searchParams.set('unread_only', 'true');
    const qs = searchParams.toString();
    const res = await apiRequest<{ data: Notification[]; total: number }>(`/api/notifications${qs ? `?${qs}` : ''}`);
    return res;
  },

  async create(input: CreateNotificationInput): Promise<{ id: number }> {
    const res = await apiRequest<{ data: { id: number } }>('/api/notifications', {
      method: 'POST',
      body: JSON.stringify(input),
    });
    return res.data;
  },

  async batchSend(input: BatchNotificationInput): Promise<{ count: number }> {
    const res = await apiRequest<{ data: { count: number } }>('/api/notifications/batch', {
      method: 'POST',
      body: JSON.stringify(input),
    });
    return res.data;
  },

  async markAsRead(id: number): Promise<void> {
    await apiRequest(`/api/notifications/${id}/read`, { method: 'PUT' });
  },

  async markAllAsRead(): Promise<void> {
    await apiRequest('/api/notifications/read-all', { method: 'PUT' });
  },

  async getUnreadCount(): Promise<number> {
    const res = await apiRequest<{ data: { count: number } }>('/api/notifications/unread-count');
    return res.data.count;
  },

  async delete(id: number): Promise<void> {
    await apiRequest(`/api/notifications/${id}`, { method: 'DELETE' });
  },

  async clearAll(): Promise<void> {
    await apiRequest('/api/notifications/clear-all', { method: 'DELETE' });
  },

  // ─── 管理员端 ─────────────────────────────────────────

  async getSent(params?: { page?: number; pageSize?: number }): Promise<{ data: Notification[]; total: number }> {
    const searchParams = new URLSearchParams();
    if (params?.page) searchParams.set('page', String(params.page));
    if (params?.pageSize) searchParams.set('page_size', String(params.pageSize));
    const qs = searchParams.toString();
    const res = await apiRequest<{ data: Notification[]; total: number }>(`/api/notifications/sent${qs ? `?${qs}` : ''}`);
    return res;
  },

  async recall(id: number): Promise<void> {
    await apiRequest(`/api/notifications/${id}/recall`, { method: 'PUT' });
  },
};
