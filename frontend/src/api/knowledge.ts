import { apiRequest } from './client';
import type {
  KnowledgeBase,
  KnowledgeBaseListItem,
  KnowledgeItem,
  KnowledgeGroup,
  OffsetPaginationResponse,
} from '../types/knowledge';

export interface CreateKnowledgeBaseInput {
  name: string;
  groupId?: string;
  dimensions?: number;
  embeddingModelId?: string;
  status?: string;
  error?: string;
  rerankModelId?: string;
  fileProcessorId?: string;
  chunkSize?: number;
  chunkOverlap?: number;
  threshold?: number;
  documentCount?: number;
  searchMode?: string;
  hybridAlpha?: number;
}

export interface UpdateKnowledgeBaseInput {
  name?: string;
  groupId?: string | null;
  rerankModelId?: string | null;
  fileProcessorId?: string | null;
  chunkSize?: number;
  chunkOverlap?: number;
  threshold?: number;
  documentCount?: number;
  searchMode?: string;
  hybridAlpha?: number | null;
  status?: string;
  error?: string;
  dimensions?: number;
  embeddingModelId?: string;
}

export interface CreateKnowledgeItemInput {
  type: 'file' | 'url' | 'note' | 'directory';
  groupId?: string | null;
  data: Record<string, any>;
}

export const knowledgeApi = {
  // ─── 知识库 CRUD ─────────────────────────────────────
  async listBases(page = 1, limit = 20): Promise<{ data: OffsetPaginationResponse<KnowledgeBaseListItem> }> {
    return apiRequest(`/api/knowledge-bases?page=${page}&limit=${limit}`);
  },

  async createBase(data: CreateKnowledgeBaseInput): Promise<{ data: KnowledgeBase }> {
    return apiRequest('/api/knowledge-bases', { method: 'POST', body: JSON.stringify(data) });
  },

  async getBase(id: string): Promise<{ data: KnowledgeBase }> {
    return apiRequest(`/api/knowledge-bases/${id}`);
  },

  async updateBase(id: string, data: UpdateKnowledgeBaseInput): Promise<{ data: KnowledgeBase }> {
    return apiRequest(`/api/knowledge-bases/${id}`, { method: 'PATCH', body: JSON.stringify(data) });
  },

  async deleteBase(id: string): Promise<void> {
    await apiRequest(`/api/knowledge-bases/${id}`, { method: 'DELETE' });
  },

  // ─── 知识项 CRUD ─────────────────────────────────────
  async listItems(baseId: string, params: { page?: number; limit?: number; type?: string; groupId?: string } = {}): Promise<{ data: OffsetPaginationResponse<KnowledgeItem> }> {
    const sp = new URLSearchParams();
    if (params.page) sp.set('page', String(params.page));
    if (params.limit) sp.set('limit', String(params.limit));
    if (params.type) sp.set('type', params.type);
    if (params.groupId) sp.set('groupId', params.groupId);
    const qs = sp.toString();
    return apiRequest(`/api/knowledge/bases/${baseId}/items${qs ? `?${qs}` : ''}`);
  },

  async createItem(baseId: string, data: CreateKnowledgeItemInput): Promise<{ data: KnowledgeItem }> {
    return apiRequest(`/api/knowledge/bases/${baseId}/items`, { method: 'POST', body: JSON.stringify(data) });
  },

  async getItem(itemId: string): Promise<{ data: KnowledgeItem }> {
    return apiRequest(`/api/knowledge/items/${itemId}`);
  },

  async updateItem(itemId: string, data: { status?: string; error?: string; data?: Record<string, any> }): Promise<{ data: KnowledgeItem }> {
    return apiRequest(`/api/knowledge/items/${itemId}`, { method: 'PATCH', body: JSON.stringify(data) });
  },

  async deleteItem(itemId: string): Promise<void> {
    await apiRequest(`/api/knowledge/items/${itemId}`, { method: 'DELETE' });
  },

  // ─── 文件上传 ────────────────────────────────────────
  async uploadFile(file: File, baseId?: string): Promise<{ data: any }> {
    const formData = new FormData();
    formData.append('file', file);
    if (baseId) formData.append('base_id', baseId);
    const token = localStorage.getItem('token');
    const res = await fetch('http://localhost:8000/api/knowledge/upload', {
      method: 'POST',
      headers: token ? { Authorization: `Bearer ${token}` } : {},
      body: formData,
    });
    return res.json();
  },

  // ─── 搜索 ────────────────────────────────────────────
  async search(params: { q: string; base_id?: string; limit?: number }): Promise<{ data: any[]; total: number }> {
    const sp = new URLSearchParams();
    sp.set('q', params.q);
    if (params.base_id) sp.set('base_id', params.base_id);
    if (params.limit) sp.set('limit', String(params.limit));
    return apiRequest(`/api/knowledge/search?${sp}`);
  },

  // ─── 模型列表 ──────────────────────────────────────
  async listEmbeddingModels(): Promise<{ data: Array<{ id: string; providerId: string; providerName: string; modelId: string; label: string }> }> {
    return apiRequest('/api/models/embedding');
  },

  async listRerankModels(): Promise<{ data: Array<{ id: string; providerId: string; providerName: string; modelId: string; label: string }> }> {
    return apiRequest('/api/models/rerank');
  },

  // ─── 分组 ─�────────────────────────────────────────────
  async listGroups(): Promise<{ data: KnowledgeGroup[] }> {
    return apiRequest('/api/knowledge/groups');
  },

  async createGroup(name: string): Promise<{ data: KnowledgeGroup }> {
    return apiRequest('/api/knowledge/groups', { method: 'POST', body: JSON.stringify({ name }) });
  },

  async deleteGroup(id: string): Promise<void> {
    await apiRequest(`/api/knowledge/groups/${id}`, { method: 'DELETE' });
  },
};

// 保留旧 API 兼容
export const knowledgeApiLegacy = {
  async listDocs(params: { base_id?: string; q?: string; page?: number; page_size?: number } = {}): Promise<{ data: any[]; total: number }> {
    const sp = new URLSearchParams();
    if (params.base_id) sp.set('base_id', params.base_id);
    if (params.q) sp.set('q', params.q);
    if (params.page) sp.set('page', String(params.page));
    if (params.page_size) sp.set('page_size', String(params.page_size));
    const qs = sp.toString();
    return apiRequest(`/api/knowledge/docs${qs ? `?${qs}` : ''}`);
  },

  async createDoc(data: { title: string; content: string; base_id?: string; category?: string; tags?: string[]; source?: string }): Promise<{ data: any }> {
    return apiRequest('/api/knowledge/docs', { method: 'POST', body: JSON.stringify(data) });
  },

  async deleteDoc(id: string): Promise<void> {
    await apiRequest(`/api/knowledge/docs/${id}`, { method: 'DELETE' });
  },
};
