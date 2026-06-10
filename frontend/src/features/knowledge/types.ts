import type { KnowledgeSearchMode } from '../../types/knowledge';

export type KnowledgeTabKey = 'data' | 'rag' | 'recall';

export interface KnowledgeSelectOption {
  label: string;
  value: string;
}

export interface KnowledgeRagConfigFormValues {
  fileProcessorId: string | null;
  chunkSize: string;
  chunkOverlap: string;
  embeddingModelId: string | null;
  rerankModelId: string | null;
  dimensions: string;
  documentCount: number;
  threshold: number;
  searchMode: KnowledgeSearchMode;
  hybridAlpha: number | null;
}

export type DataSourceSourceType = 'file' | 'url' | 'note' | 'directory';

export type KnowledgeRagChunkValidationErrorCode =
  | 'chunkSizeInvalid'
  | 'chunkOverlapInvalid'
  | 'chunkOverlapMustBeSmaller';

export type KnowledgeRagDimensionsValidationErrorCode = 'dimensionsInvalid';

export interface KnowledgeRagChunkValidationErrors {
  chunkOverlap?: KnowledgeRagChunkValidationErrorCode;
  chunkSize?: KnowledgeRagChunkValidationErrorCode;
  dimensions?: KnowledgeRagDimensionsValidationErrorCode;
}

export interface KnowledgePageBaseGroupSection {
  groupId: string | null;
  items: import('../../types/knowledge').KnowledgeBaseListItem[];
}
