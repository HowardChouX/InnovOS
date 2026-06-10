import { useState, useEffect, useMemo, useCallback } from 'react';
import { useTranslation } from 'react-i18next';
import { knowledgeApi } from '../../../api/knowledge';
import type { KnowledgeBase } from '../../../types/knowledge';
import type { KnowledgeRagConfigFormValues, KnowledgeSelectOption } from '../types';
import {
  createKnowledgeRagConfigFormValues,
  buildKnowledgeRagConfigPatch,
  normalizeKnowledgeError,
} from '../utils';

const FILE_PROCESSOR_OPTIONS: KnowledgeSelectOption[] = [
  { value: 'default', label: '默认 (Document → Markdown)' },
  { value: 'naive', label: '朴素 (文本提取)' },
];

interface ModelOption {
  id: string;
  providerId: string;
  modelId: string;
}

const formatModelOptionLabel = (model: ModelOption): string => {
  return `${model.modelId} · ${model.providerId}`;
};

/**
 * Hook providing RAG configuration state and save action for a knowledge base.
 *
 * Returns initial form values, model/file processor/search mode option lists,
 * a save function, and loading/error states.
 */
export const useKnowledgeRagConfig = (base: KnowledgeBase) => {
  const { t } = useTranslation();

  const [embeddingModels, setEmbeddingModels] = useState<ModelOption[]>([]);
  const [rerankModels, setRerankModels] = useState<ModelOption[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<Error | null>(null);

  useEffect(() => {
    knowledgeApi.listEmbeddingModels().then((res) => {
      setEmbeddingModels(res.data || []);
    }).catch(() => { /* silently ignore — models may not be configured yet */ });

    knowledgeApi.listRerankModels().then((res) => {
      setRerankModels(res.data || []);
    }).catch(() => { /* silently ignore */ });
  }, []);

  const initialValues = useMemo(() => createKnowledgeRagConfigFormValues(base), [base]);

  const fileProcessorOptions = useMemo(() => FILE_PROCESSOR_OPTIONS, []);

  const embeddingModelOptions = useMemo<KnowledgeSelectOption[]>(() => {
    return embeddingModels.map((model) => ({
      value: model.id,
      label: formatModelOptionLabel(model),
    }));
  }, [embeddingModels]);

  const rerankModelOptions = useMemo<KnowledgeSelectOption[]>(() => {
    return rerankModels.map((model) => ({
      value: model.id,
      label: formatModelOptionLabel(model),
    }));
  }, [rerankModels]);

  const searchModeOptions = useMemo<KnowledgeSelectOption[]>(
    () => [
      { value: 'hybrid', label: t('knowledge.rag.search_mode.hybrid') },
      { value: 'default', label: t('knowledge.rag.search_mode.default') },
      { value: 'bm25', label: t('knowledge.rag.search_mode.bm25') },
    ],
    [t]
  );

  const save = useCallback(
    async (values: KnowledgeRagConfigFormValues) => {
      const patch = buildKnowledgeRagConfigPatch(initialValues, values);

      setIsLoading(true);
      setError(null);

      try {
        return await knowledgeApi.updateBase(base.id, patch);
      } catch (saveError) {
        const normalizedError = normalizeKnowledgeError(saveError);
        setError(normalizedError);
        throw normalizedError;
      } finally {
        setIsLoading(false);
      }
    },
    [base.id, initialValues]
  );

  return {
    initialValues,
    embeddingModels,
    fileProcessorOptions,
    embeddingModelOptions,
    rerankModelOptions,
    searchModeOptions,
    save,
    isLoading,
    error,
  };
};
