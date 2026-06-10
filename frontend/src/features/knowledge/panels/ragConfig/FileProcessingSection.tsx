import { RagFieldLabel, RagSelectField } from './panelPrimitives'

const EMPTY_OPTION_VALUE = '__none__'

interface FileProcessingSectionProps {
  fileProcessorId: string | null
  fileProcessorOptions: { label: string; value: string }[]
  onFileProcessorChange: (value: string | null) => void
}

export default function FileProcessingSection({
  fileProcessorId,
  fileProcessorOptions,
  onFileProcessorChange
}: FileProcessingSectionProps) {
  return (
    <div>
      <RagFieldLabel label="文件处理器" hint="用于将文件转换为文本的处理器" />
      <RagSelectField
        value={fileProcessorId ?? EMPTY_OPTION_VALUE}
        options={[{ value: EMPTY_OPTION_VALUE, label: '未设置' }, ...fileProcessorOptions]}
        onValueChange={(value) => onFileProcessorChange(value === EMPTY_OPTION_VALUE ? null : value)}
      />
    </div>
  )
}
