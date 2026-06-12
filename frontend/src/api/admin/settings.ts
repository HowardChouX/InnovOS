import { apiRequest } from '../client';

/** 可用模型条目 */
export interface AvailableModel {
  providerId: string;
  modelId: string;
  name: string;
  capabilities: string[];
}

/** 模型分配配置 */
export interface AssignedModels {
  chat_model: string | null;
  embedding_model: string | null;
  rerank_model: string | null;
  ocr_model: string | null;
}

/** 按能力分组的可用模型 */
export interface AvailableModelsByCapability {
  chat: AvailableModel[];
  embedding: AvailableModel[];
  rerank: AvailableModel[];
  vision: AvailableModel[];
}

/** 全局 RAG 配置 */
export interface RagConfig {
  chunk_size: string | null;
  chunk_overlap: string | null;
  search_mode: string | null;
  hybrid_alpha: string | null;
  threshold: string | null;
  document_count: string | null;
  file_processor: string | null;
}

export const settingsApi = {
  /** 获取当前模型分配 */
  getAssigned: (): Promise<{ data: AssignedModels }> =>
    apiRequest('/api/admin/settings/models/assigned'),

  /** 保存模型分配 */
  setAssigned: (data: Partial<AssignedModels>): Promise<{ message: string }> =>
    apiRequest('/api/admin/settings/models/assigned', {
      method: 'PUT',
      body: JSON.stringify(data),
    }),

  /** 获取所有可用模型（按能力分组） */
  getAvailable: (): Promise<{ data: AvailableModelsByCapability }> =>
    apiRequest('/api/admin/settings/models/available'),

  /** 获取全局 RAG 配置 */
  getRagConfig: (): Promise<{ data: RagConfig }> =>
    apiRequest('/api/admin/settings/rag'),

  /** 保存全局 RAG 配置 */
  setRagConfig: (data: Partial<RagConfig>): Promise<{ message: string }> =>
    apiRequest('/api/admin/settings/rag', {
      method: 'PUT',
      body: JSON.stringify(data),
    }),
};
