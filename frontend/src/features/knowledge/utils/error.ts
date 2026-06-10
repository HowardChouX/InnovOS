import type { KnowledgeBase } from '../../../types/knowledge';

/** Error code stored on a KnowledgeBase when its embedding model is missing. */
export const KNOWLEDGE_BASE_ERROR_MISSING_EMBEDDING_MODEL = 'missing_embedding_model';

type KnowledgeErrorTranslator = (key: string) => string;

/**
 * Extract a human-readable message from an unknown error.
 */
export const getErrorMessage = (error: unknown): string => {
  if (error instanceof Error) return error.message;
  if (typeof error === 'string') return error;
  if (error && typeof error === 'object') {
    const obj = error as Record<string, unknown>;
    if (typeof obj.message === 'string') return obj.message;
    if (typeof obj.detail === 'string') return obj.detail;
  }
  return String(error);
};

/**
 * Normalize an unknown error value into an Error instance.
 */
export const normalizeKnowledgeError = (error: unknown): Error => {
  if (error instanceof Error) return error;
  return new Error(String(error));
};

/**
 * Get the human-readable failure reason for a knowledge base.
 */
export const getKnowledgeBaseFailureReason = (
  base: Pick<KnowledgeBase, 'error'>,
  t: KnowledgeErrorTranslator
) => {
  if (base.error === KNOWLEDGE_BASE_ERROR_MISSING_EMBEDDING_MODEL) {
    return t('knowledge.error.missing_embedding_model');
  }
  return base.error ?? t('knowledge.error.failed_base_unknown');
};
