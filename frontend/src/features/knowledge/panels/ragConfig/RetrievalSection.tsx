import type { KnowledgeSearchMode } from '../../../../types/knowledge'
import { RagFieldLabel, RagSelectField, RagSliderField } from './panelPrimitives'

const EMPTY_OPTION_VALUE = '__none__'
const DEFAULT_HYBRID_ALPHA = 0.5

interface RetrievalSectionProps {
  searchModeOptions: { label: string; value: string }[]
  rerankModelOptions: { label: string; value: string }[]
  documentCount: number
  threshold: number
  searchMode: KnowledgeSearchMode
  hybridAlpha: number | null
  rerankModelId: string | null
  onDocumentCountChange: (value: number) => void
  onThresholdChange: (value: number) => void
  onSearchModeChange: (value: KnowledgeSearchMode) => void
  onHybridAlphaChange: (value: number) => void
  onRerankModelChange: (value: string | null) => void
}

export default function RetrievalSection({
  searchModeOptions,
  rerankModelOptions,
  documentCount,
  threshold,
  searchMode,
  hybridAlpha,
  rerankModelId,
  onDocumentCountChange,
  onThresholdChange,
  onSearchModeChange,
  onHybridAlphaChange,
  onRerankModelChange
}: RetrievalSectionProps) {
  const isHybridMode = searchMode === 'hybrid'
  const usesRelevanceThreshold = searchMode === 'default' || rerankModelId !== null

  return (
    <div className="flex flex-col gap-4">
      <RagSliderField
        label="返回结果数"
        hint="每次检索返回的最大文档数量"
        value={documentCount}
        onValueChange={onDocumentCountChange}
        min={1}
        max={50}
        step={1}
        minLabel="1"
        maxLabel="50"
        formatValue={(value) => String(value)}
      />

      {usesRelevanceThreshold ? (
        <RagSliderField
          label="相关性阈值"
          hint="过滤低相关性结果的阈值"
          value={threshold}
          onValueChange={onThresholdChange}
          min={0}
          max={1}
          step={0.1}
          minLabel="0.0"
          maxLabel="1.0"
          formatValue={(value) => value.toFixed(1)}
        />
      ) : null}

      <div>
        <RagFieldLabel label="搜索模式" hint="选择检索时使用的搜索策略" />
        <RagSelectField
          value={searchMode}
          options={searchModeOptions}
          onValueChange={(value) => onSearchModeChange(value as KnowledgeSearchMode)}
        />
      </div>

      {isHybridMode ? (
        <RagSliderField
          label="混合权重"
          hint="向量检索与关键词检索的混合比例"
          value={hybridAlpha ?? DEFAULT_HYBRID_ALPHA}
          onValueChange={onHybridAlphaChange}
          min={0}
          max={1}
          step={0.1}
          minLabel="0.0"
          maxLabel="1.0"
          formatValue={(value) => value.toFixed(1)}
        />
      ) : null}

      <div>
        <RagFieldLabel label="重排序模型" hint="对检索结果进行重排序的模型" />
        <RagSelectField
          value={rerankModelId ?? EMPTY_OPTION_VALUE}
          options={[{ value: EMPTY_OPTION_VALUE, label: '禁用重排序' }, ...rerankModelOptions]}
          onValueChange={(value) => onRerankModelChange(value === EMPTY_OPTION_VALUE ? null : value)}
        />
      </div>
    </div>
  )
}
