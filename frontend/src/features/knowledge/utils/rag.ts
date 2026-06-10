import type { KnowledgeBase } from '../../../types/knowledge';
import type { KnowledgeRagConfigFormValues } from '../types';
import { parseRequiredInteger } from './validate';

export const DEFAULT_KNOWLEDGE_DOCUMENT_COUNT = 6;
export const DEFAULT_KNOWLEDGE_THRESHOLD = 0.0;

/**
 * Extract RAG config form values from a KnowledgeBase object.
 */
export const createKnowledgeRagConfigFormValues = (
  base: KnowledgeBase
): KnowledgeRagConfigFormValues => ({
  fileProcessorId: base.fileProcessorId ?? null,
  chunkSize: String(base.chunkSize),
  chunkOverlap: String(base.chunkOverlap),
  embeddingModelId: base.embeddingModelId,
  rerankModelId: base.rerankModelId ?? null,
  dimensions: base.dimensions == null ? '' : String(base.dimensions),
  documentCount: base.documentCount ?? DEFAULT_KNOWLEDGE_DOCUMENT_COUNT,
  threshold: base.threshold ?? DEFAULT_KNOWLEDGE_THRESHOLD,
  searchMode: base.searchMode,
  hybridAlpha: base.hybridAlpha ?? null,
});

/**
 * Build a partial update payload containing only changed fields.
 */
export const buildKnowledgeRagConfigPatch = (
  initialValues: KnowledgeRagConfigFormValues,
  currentValues: KnowledgeRagConfigFormValues
): Record<string, any> => {
  const patch: Record<string, any> = {};

  if (currentValues.fileProcessorId !== initialValues.fileProcessorId) {
    patch.fileProcessorId = currentValues.fileProcessorId;
  }

  if (currentValues.chunkSize !== initialValues.chunkSize) {
    patch.chunkSize = parseRequiredInteger(currentValues.chunkSize);
  }

  if (currentValues.chunkOverlap !== initialValues.chunkOverlap) {
    patch.chunkOverlap = parseRequiredInteger(currentValues.chunkOverlap);
  }

  if (currentValues.rerankModelId !== initialValues.rerankModelId) {
    patch.rerankModelId = currentValues.rerankModelId;
  }

  if (currentValues.documentCount !== initialValues.documentCount) {
    patch.documentCount = currentValues.documentCount;
  }

  if (currentValues.threshold !== initialValues.threshold) {
    patch.threshold = currentValues.threshold;
  }

  if (currentValues.searchMode !== initialValues.searchMode) {
    patch.searchMode = currentValues.searchMode;
  }

  if (
    currentValues.searchMode === 'hybrid' &&
    currentValues.hybridAlpha !== initialValues.hybridAlpha
  ) {
    patch.hybridAlpha = currentValues.hybridAlpha ?? undefined;
  }

  return patch;
};
