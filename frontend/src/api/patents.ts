import type { Patent, PatentStats } from '../types/patent';
import { apiRequest } from './client';

export interface PatentSearchParams {
  q?: string;
  page?: number;
  page_size?: number;
  ipc_code?: string;
  applicant?: string;
  sort_by?: string;
  order?: string;
}

export interface PatentSearchResult {
  data: Patent[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

export interface SemanticResult {
  itemId: string;
  text: string;
  patentId: string;
  score: number;
  chunkIndex: number;
  title?: string;
  patentNumber?: string;
}

export const patentsApi = {
  async search(params: PatentSearchParams): Promise<PatentSearchResult> {
    const searchParams = new URLSearchParams();
    if (params.q) searchParams.set('q', params.q);
    if (params.page) searchParams.set('page', String(params.page));
    if (params.page_size) searchParams.set('page_size', String(params.page_size));
    if (params.ipc_code) searchParams.set('ipc_code', params.ipc_code);
    if (params.applicant) searchParams.set('applicant', params.applicant);
    if (params.sort_by) searchParams.set('sort_by', params.sort_by);
    if (params.order) searchParams.set('order', params.order);
    
    const qs = searchParams.toString();
    const res = await apiRequest<PatentSearchResult>(`/api/patents/search${qs ? `?${qs}` : ''}`);
    return res;
  },

  async semanticSearch(query: string, topK: number = 10): Promise<{ data: SemanticResult[]; total: number }> {
    const qs = new URLSearchParams({ q: query, top_k: String(topK) }).toString();
    return apiRequest(`/api/patents/semantic-search?${qs}`);
  },

  async getDetail(patentId: string): Promise<Patent> {
    const res = await apiRequest<{ data: Patent }>(`/api/patents/${patentId}`);
    return res.data;
  },

  async getStats(): Promise<PatentStats> {
    const res = await apiRequest<{ data: PatentStats }>('/api/patents/stats');
    return res.data;
  },
};
