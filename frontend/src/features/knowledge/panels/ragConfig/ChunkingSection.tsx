import { RagHintText, RagNumericField } from './panelPrimitives'

export type KnowledgeRagChunkValidationErrorCode =
  | 'chunkSizeInvalid'
  | 'chunkOverlapInvalid'
  | 'chunkOverlapMustBeSmaller'

interface ChunkingSectionProps {
  chunkSize: string
  chunkOverlap: string
  chunkSizeErrorCode?: KnowledgeRagChunkValidationErrorCode
  chunkOverlapErrorCode?: KnowledgeRagChunkValidationErrorCode
  onChunkSizeChange: (value: string) => void
  onChunkOverlapChange: (value: string) => void
}

export default function ChunkingSection({
  chunkSize,
  chunkOverlap,
  chunkSizeErrorCode,
  chunkOverlapErrorCode,
  onChunkSizeChange,
  onChunkOverlapChange
}: ChunkingSectionProps) {
  const getValidationErrorMessage = (errorCode?: KnowledgeRagChunkValidationErrorCode) => {
    switch (errorCode) {
      case 'chunkSizeInvalid':
        return '分块大小必须为正整数'
      case 'chunkOverlapInvalid':
        return '重叠大小必须为非负整数'
      case 'chunkOverlapMustBeSmaller':
        return '重叠大小必须小于分块大小'
      default:
        return undefined
    }
  }

  return (
    <div className="space-y-2">
      <div className="flex flex-col gap-4">
        <RagNumericField
          label="分块大小"
          hint="每个文本块的最大 token 数量"
          value={chunkSize}
          suffix="tokens"
          onChange={onChunkSizeChange}
        />
        <RagNumericField
          label="重叠大小"
          hint="相邻文本块之间的重叠 token 数量"
          value={chunkOverlap}
          suffix="tokens"
          onChange={onChunkOverlapChange}
        />
      </div>

      {chunkSizeErrorCode ? (
        <RagHintText tone="error">{getValidationErrorMessage(chunkSizeErrorCode)}</RagHintText>
      ) : null}
      {chunkOverlapErrorCode ? (
        <RagHintText tone="error">{getValidationErrorMessage(chunkOverlapErrorCode)}</RagHintText>
      ) : null}
      <RagHintText tone="warning">修改分块大小或重叠大小后，需要重新索引所有数据源</RagHintText>
    </div>
  )
}
