import type { KnowledgeDoc, KnowledgeCategory } from '../types/knowledge';
import { apiRequest } from './client';

export interface DocListParams {
  q?: string;
  category?: string;
  page?: number;
  page_size?: number;
}

export interface DocListResult {
  data: KnowledgeDoc[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

export const knowledgeApi = {
  async listDocs(params: DocListParams): Promise<DocListResult> {
    const searchParams = new URLSearchParams();
    if (params.q) searchParams.set('q', params.q);
    if (params.category) searchParams.set('category', params.category);
    if (params.page) searchParams.set('page', String(params.page));
    if (params.page_size) searchParams.set('page_size', String(params.page_size));
    const qs = searchParams.toString();
    const res = await apiRequest<DocListResult>(`/api/knowledge/docs${qs ? `?${qs}` : ''}`);
    return res;
  },

  async getDoc(id: string): Promise<KnowledgeDoc> {
    const res = await apiRequest<{ data: KnowledgeDoc }>(`/api/knowledge/docs/${id}`);
    return res.data;
  },

  async createDoc(data: {
    title: string;
    content: string;
    category?: string;
    tags?: string[];
    source?: string;
  }): Promise<KnowledgeDoc> {
    const res = await apiRequest<{ data: KnowledgeDoc }>('/api/knowledge/docs', {
      method: 'POST',
      body: JSON.stringify(data),
    });
    return res.data;
  },

  async updateDoc(id: string, data: Partial<KnowledgeDoc>): Promise<KnowledgeDoc> {
    const res = await apiRequest<{ data: KnowledgeDoc }>(`/api/knowledge/docs/${id}`, {
      method: 'PUT',
      body: JSON.stringify(data),
    });
    return res.data;
  },

  async deleteDoc(id: string): Promise<void> {
    await apiRequest(`/api/knowledge/docs/${id}`, { method: 'DELETE' });
  },

  async listCategories(): Promise<{ data: KnowledgeCategory[] }> {
    const res = await apiRequest<{ data: KnowledgeCategory[] }>('/api/knowledge/categories');
    return res;
  },

  async search(q: string, limit?: number): Promise<{ data: KnowledgeDoc[]; total: number }> {
    const searchParams = new URLSearchParams();
    searchParams.set('q', q);
    if (limit) searchParams.set('limit', String(limit));
    const res = await apiRequest<{ data: KnowledgeDoc[]; total: number }>(`/api/knowledge/search?${searchParams.toString()}`);
    return res;
  },
};
