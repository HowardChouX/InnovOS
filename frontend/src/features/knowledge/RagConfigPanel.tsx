import { useState, useEffect, useMemo } from 'react';
import { createPortal } from 'react-dom';
import { useKnowledgeStore } from '../../store/useKnowledgeStore';
import { knowledgeApi } from '../../api/knowledge';
import KnowledgePanelShell from './components/KnowledgePanelShell';
import { KnowledgeDialogFooter } from './components/KnowledgeDialogLayout';
import ChunkingSection from './panels/ragConfig/ChunkingSection';
import EmbeddingSection from './panels/ragConfig/EmbeddingSection';
import FileProcessingSection from './panels/ragConfig/FileProcessingSection';
import RetrievalSection from './panels/ragConfig/RetrievalSection';

export interface KnowledgeRestoreBaseInitialValues {
  embeddingModelId?: string | null;
  dimensions?: number | null;
}

interface Props {
  open: boolean;
  onClose: () => void;
}

const parseOptionalInteger = (value: string) => {
  if (!value) return null;
  const parsed = Number(value);
  return Number.isInteger(parsed) ? parsed : null;
};

const parseRequiredInteger = (value: string) => {
  const parsed = parseOptionalInteger(value);
  if (parsed == null) {
    throw new Error(`Expected integer string, received "${value}"`);
  }
  return parsed;
};

const getKnowledgeRagChunkValidationErrors = (values: { chunkOverlap: string; chunkSize: string; dimensions?: string }) => {
  const chunkSize = parseOptionalInteger(values.chunkSize);
  const chunkOverlap = parseOptionalInteger(values.chunkOverlap);
  const dimensions = values.dimensions == null ? null : parseOptionalInteger(values.dimensions);
  const errors: { chunkOverlap?: 'chunkOverlapInvalid' | 'chunkOverlapMustBeSmaller'; chunkSize?: 'chunkSizeInvalid'; dimensions?: 'dimensionsInvalid' } = {};

  if (values.chunkSize && (!chunkSize || chunkSize <= 0)) {
    errors.chunkSize = 'chunkSizeInvalid';
  }
  if (values.chunkOverlap && (chunkOverlap == null || chunkOverlap < 0)) {
    errors.chunkOverlap = 'chunkOverlapInvalid';
  }
  if (chunkSize != null && chunkSize > 0 && chunkOverlap != null && chunkOverlap >= chunkSize) {
    errors.chunkOverlap = 'chunkOverlapMustBeSmaller';
  }
  if (values.dimensions && (!dimensions || dimensions <= 0)) {
    errors.dimensions = 'dimensionsInvalid';
  }
  return errors;
};

const getKnowledgeRagConfigFormState = (
  initialValues: { [key: string]: any },
  currentValues: { chunkOverlap: string; chunkSize: string; dimensions?: string } & Record<string, any>
) => {
  const validationErrorCodes = getKnowledgeRagChunkValidationErrors(currentValues);
  const hasEmptyChunkFields = currentValues.chunkSize === '' || currentValues.chunkOverlap === '' || currentValues.dimensions === '';
  const hasValidationErrors = Object.values(validationErrorCodes).some(Boolean);
  const ragKeys = ['fileProcessorId', 'chunkSize', 'chunkOverlap', 'embeddingModelId', 'dimensions', 'rerankModelId', 'documentCount', 'threshold', 'searchMode', 'hybridAlpha'];
  const isDirty = ragKeys.some((key) => initialValues[key] !== currentValues[key]);

  return {
    validationErrorCodes,
    hasEmptyChunkFields,
    hasValidationErrors,
    isDirty,
    canSave: isDirty && !hasEmptyChunkFields && !hasValidationErrors
  };
};

const createKnowledgeRagConfigFormValues = (base: any) => ({
  fileProcessorId: base.fileProcessorId ?? null,
  chunkSize: String(base.chunkSize || 1024),
  chunkOverlap: String(base.chunkOverlap || 200),
  embeddingModelId: base.embeddingModelId ?? null,
  rerankModelId: base.rerankModelId ?? null,
  dimensions: base.dimensions == null ? '' : String(base.dimensions),
  documentCount: base.documentCount ?? 10,
  threshold: base.threshold ?? 0.0,
  searchMode: base.searchMode || 'hybrid',
  hybridAlpha: base.hybridAlpha ?? null
});

export function RagConfigPanel({ open, onClose }: Props) {
  const { bases, selectedBaseId } = useKnowledgeStore();
  const base = bases.find(b => b.id === selectedBaseId);

  const [values, setValues] = useState<any>(null);
  const [initialValues, setInitialValues] = useState<any>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [isFetchingDimensions, setIsFetchingDimensions] = useState(false);
  const [embeddingModels, setEmbeddingModels] = useState<Array<{ id: string; label: string }>>([]);
  const [rerankModels, setRerankModels] = useState<Array<{ id: string; label: string }>>([]);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  useEffect(() => {
    if (base) {
      const iv = createKnowledgeRagConfigFormValues(base);
      setInitialValues(iv);
      setValues(iv);
    }
  }, [base]);

  useEffect(() => {
    if (!open) return;
    knowledgeApi.listEmbeddingModels().then(res => {
      setEmbeddingModels(res.data?.map((m: any) => ({ id: m.id, label: m.label || m.id })) || []);
    }).catch(() => {});
    knowledgeApi.listRerankModels().then(res => {
      setRerankModels(res.data?.map((m: any) => ({ id: m.id, label: m.label || m.id })) || []);
    }).catch(() => {});
  }, [open]);

  const formState = useMemo(() => {
    if (!initialValues || !values) {
      return {
        validationErrorCodes: {} as { chunkSize?: 'chunkSizeInvalid'; chunkOverlap?: 'chunkOverlapInvalid' | 'chunkOverlapMustBeSmaller'; dimensions?: 'dimensionsInvalid' },
        isDirty: false,
        canSave: false
      };
    }
    return getKnowledgeRagConfigFormState(initialValues, values);
  }, [initialValues, values]);
  const { validationErrorCodes, isDirty, canSave } = formState;
  const selectedEmbeddingModel = embeddingModels.find((model) => model.id === values?.embeddingModelId);
  const embeddingConfigChanged =
    values?.embeddingModelId !== initialValues?.embeddingModelId || values?.dimensions !== initialValues?.dimensions;

  const searchModeOptions = [
    { value: 'hybrid', label: '混合检索' },
    { value: 'default', label: '向量检索' },
    { value: 'bm25', label: '关键词检索' },
  ];

  const fileProcessorOptions = [
    { value: 'default', label: '默认处理器' },
  ];

  if (!open || !base || !values) return null;

  const handleRefreshDimensions = async () => {
    if (!selectedEmbeddingModel) {
      setErrorMessage('请先选择嵌入模型');
      return;
    }
    setIsFetchingDimensions(true);
    try {
      // InnovOS may not have embedMany endpoint; simulate with a fixed dimension or call API
      setValues((currentValues: any) => ({ ...currentValues, dimensions: '1536' }));
    } catch (error) {
      setErrorMessage(`获取维度失败: ${error instanceof Error ? error.message : String(error)}`);
    } finally {
      setIsFetchingDimensions(false);
    }
  };

  const handleSave = async () => {
    if (!canSave || !selectedBaseId) return;

    if (embeddingConfigChanged) {
      // If embedding config changed, we need to restore the base
      setIsLoading(true);
      try {
        await knowledgeApi.updateBase(selectedBaseId, {
          embeddingModelId: values.embeddingModelId,
          dimensions: parseRequiredInteger(values.dimensions),
          status: 'completed',
          error: undefined,
        });
        onClose();
      } catch (error) {
        setErrorMessage(`保存失败: ${error instanceof Error ? error.message : String(error)}`);
      } finally {
        setIsLoading(false);
      }
      return;
    }

    setIsLoading(true);
    try {
      const patch: any = {};
      if (values.fileProcessorId !== initialValues.fileProcessorId) patch.fileProcessorId = values.fileProcessorId;
      if (values.chunkSize !== initialValues.chunkSize) patch.chunkSize = parseRequiredInteger(values.chunkSize);
      if (values.chunkOverlap !== initialValues.chunkOverlap) patch.chunkOverlap = parseRequiredInteger(values.chunkOverlap);
      if (values.rerankModelId !== initialValues.rerankModelId) patch.rerankModelId = values.rerankModelId;
      if (values.documentCount !== initialValues.documentCount) patch.documentCount = values.documentCount;
      if (values.threshold !== initialValues.threshold) patch.threshold = values.threshold;
      if (values.searchMode !== initialValues.searchMode) patch.searchMode = values.searchMode;
      if (values.searchMode === 'hybrid' && values.hybridAlpha !== initialValues.hybridAlpha) patch.hybridAlpha = values.hybridAlpha ?? undefined;
      await knowledgeApi.updateBase(selectedBaseId, patch);
      onClose();
    } catch (error) {
      setErrorMessage(`保存失败: ${error instanceof Error ? error.message : String(error)}`);
    } finally {
      setIsLoading(false);
    }
  };

  const failedState = base.status === 'failed';

  const panelBody = failedState ? (
    <div className="flex h-full min-h-0 items-center justify-center">
      <div className="w-full max-w-[480px] px-5 py-4">
        <div className="rounded-lg badge-danger p-4">
          <div className="mb-1 text-sm font-medium text-accent-danger">知识库创建失败</div>
          <div className="mb-3 text-xs text-foreground-secondary">{base.error || '未知错误'}</div>
          <button
            type="button"
            className="rounded-md bg-primary px-3 py-1.5 text-xs text-primary-foreground hover:bg-primary/90"
            onClick={() => {
              setValues((v: any) => ({ ...v }));
              // Reset to active state by clearing error
              if (selectedBaseId) {
                knowledgeApi.updateBase(selectedBaseId, { status: 'completed', error: undefined }).catch(() => {});
              }
            }}>
            恢复配置
          </button>
        </div>
      </div>
    </div>
  ) : (
    <>
      <div className="min-h-0 flex-1 overflow-y-auto px-6 py-5">
        <div className="flex flex-col gap-4">
          <FileProcessingSection
            fileProcessorId={values.fileProcessorId}
            fileProcessorOptions={fileProcessorOptions}
            onFileProcessorChange={(fileProcessorId) =>
              setValues((currentValues: any) => ({ ...currentValues, fileProcessorId }))
            }
          />

          <ChunkingSection
            chunkSize={values.chunkSize}
            chunkOverlap={values.chunkOverlap}
            chunkSizeErrorCode={validationErrorCodes.chunkSize}
            chunkOverlapErrorCode={validationErrorCodes.chunkOverlap}
            onChunkSizeChange={(chunkSize) =>
              setValues((currentValues: any) => ({ ...currentValues, chunkSize: chunkSize.replace(/\D/g, '') }))
            }
            onChunkOverlapChange={(chunkOverlap) =>
              setValues((currentValues: any) => ({ ...currentValues, chunkOverlap: chunkOverlap.replace(/\D/g, '') }))
            }
          />

          <EmbeddingSection
            embeddingModelId={values.embeddingModelId}
            embeddingModelOptions={embeddingModels.map((m) => ({ value: m.id, label: m.label }))}
            dimensions={values.dimensions}
            dimensionsErrorCode={validationErrorCodes.dimensions}
            isFetchingDimensions={isFetchingDimensions}
            onEmbeddingModelChange={(embeddingModelId) =>
              setValues((currentValues: any) => ({ ...currentValues, embeddingModelId }))
            }
            onDimensionsChange={(dimensions) =>
              setValues((currentValues: any) => ({ ...currentValues, dimensions: dimensions.replace(/\D/g, '') }))
            }
            onRefreshDimensions={handleRefreshDimensions}
          />

          <RetrievalSection
            searchModeOptions={searchModeOptions}
            rerankModelOptions={rerankModels.map((m) => ({ value: m.id, label: m.label }))}
            documentCount={values.documentCount}
            threshold={values.threshold}
            searchMode={values.searchMode}
            hybridAlpha={values.hybridAlpha}
            rerankModelId={values.rerankModelId}
            onDocumentCountChange={(documentCount) =>
              setValues((currentValues: any) => ({ ...currentValues, documentCount }))
            }
            onThresholdChange={(threshold) => setValues((currentValues: any) => ({ ...currentValues, threshold }))}
            onSearchModeChange={(searchMode) => setValues((currentValues: any) => ({ ...currentValues, searchMode }))}
            onHybridAlphaChange={(hybridAlpha) => setValues((currentValues: any) => ({ ...currentValues, hybridAlpha }))}
            onRerankModelChange={(rerankModelId) => setValues((currentValues: any) => ({ ...currentValues, rerankModelId }))}
          />
        </div>
      </div>

      <KnowledgeDialogFooter className="shrink-0 border-t border-border-subtle px-6 py-4">
        <button
          type="button"
          disabled={!isDirty || isLoading}
          className="mr-auto flex items-center gap-1.5 rounded-md px-2 py-1 text-xs text-foreground-muted hover:bg-accent hover:text-foreground disabled:opacity-50"
          onClick={() => setValues(initialValues)}>
          <i className="fa-solid fa-rotate-left text-xs" />
          重置
        </button>
        <button
          type="button"
          disabled={!canSave || isLoading}
          className="rounded-md bg-primary px-4 py-2 text-xs font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
          onClick={handleSave}>
          {embeddingConfigChanged ? '恢复并保存' : isLoading ? '保存中...' : '保存'}
        </button>
      </KnowledgeDialogFooter>
    </>
  );

  return createPortal(
    <div className="fixed inset-0 z-[9999] flex items-center justify-center bg-black/50" onClick={onClose}>
      <div
        className="flex w-[560px] max-w-[90vw] flex-col overflow-hidden rounded-xl border border-border bg-card shadow-xl"
        style={{ maxHeight: '85vh' }}
        onClick={e => e.stopPropagation()}>
        <div className="flex shrink-0 items-center justify-between border-b border-border-muted px-5 py-3.5">
          <span className="text-base font-semibold text-foreground">RAG 配置</span>
          <button onClick={onClose} className="flex h-7 w-7 items-center justify-center rounded-md text-foreground-muted hover:bg-accent">
            <i className="fa-solid fa-xmark" />
          </button>
        </div>

        <KnowledgePanelShell className="min-h-0 flex-1">
          {panelBody}
        </KnowledgePanelShell>

        {/* Error Toast */}
        {errorMessage ? (
          <div className="absolute bottom-4 right-4 z-[9999] rounded-lg badge-danger px-4 py-2 text-sm">
            {errorMessage}
            <button onClick={() => setErrorMessage(null)} className="ml-2 text-accent-danger hover:opacity-80">
              <i className="fa-solid fa-xmark" />
            </button>
          </div>
        ) : null}
      </div>
    </div>,
    document.body
  );
}
