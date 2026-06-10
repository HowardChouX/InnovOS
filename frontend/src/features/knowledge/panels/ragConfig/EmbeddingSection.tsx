import type { KnowledgeSelectOption } from './panelPrimitives'
import { RagFieldLabel, RagNumericField, RagSelectField } from './panelPrimitives'

interface EmbeddingSectionProps {
  embeddingModelId: string | null
  embeddingModelOptions: KnowledgeSelectOption[]
  dimensions: string
  dimensionsErrorCode?: 'dimensionsInvalid'
  isFetchingDimensions?: boolean
  onEmbeddingModelChange: (embeddingModelId: string) => void
  onDimensionsChange: (dimensions: string) => void
  onRefreshDimensions: () => void
}

export default function EmbeddingSection({
  embeddingModelId,
  embeddingModelOptions,
  dimensions,
  dimensionsErrorCode,
  isFetchingDimensions = false,
  onEmbeddingModelChange,
  onDimensionsChange,
  onRefreshDimensions
}: EmbeddingSectionProps) {
  return (
    <div className="flex flex-col gap-4">
      <div>
        <RagFieldLabel label="嵌入模型" hint="用于将文本转换为向量表示的模型" />
        <RagSelectField
          value={embeddingModelId ?? undefined}
          options={embeddingModelOptions}
          placeholder="未设置"
          onValueChange={onEmbeddingModelChange}
        />
      </div>

      <div>
        <RagFieldLabel label="向量维度" hint="嵌入向量的维度数量" />
        <div className="flex items-center gap-2">
          <div className="min-w-0 flex-1">
            <RagNumericField value={dimensions} onChange={onDimensionsChange} />
          </div>
          <button
            type="button"
            disabled={!embeddingModelId || isFetchingDimensions}
            aria-label="刷新维度"
            onClick={onRefreshDimensions}
            className="flex shrink-0 items-center justify-center rounded-md border border-border bg-background-muted p-2 text-foreground-muted hover:bg-accent disabled:opacity-50">
            <i className={`fa-solid fa-rotate text-xs ${isFetchingDimensions ? 'animate-spin' : ''}`} />
          </button>
        </div>
        {dimensionsErrorCode === 'dimensionsInvalid' ? (
          <div className="mt-1 text-xs leading-4 text-accent-danger">维度必须为正整数</div>
        ) : null}
      </div>
    </div>
  )
}
