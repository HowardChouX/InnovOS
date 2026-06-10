import type { KnowledgeItemType } from '../../../../types/knowledge'
import { useCallback, useEffect, useRef, useState } from 'react'

interface DataSourcePanelHeaderProps {
  readyCount: number
  totalCount: number
  selectedCount: number
  onBulkReindex: () => void
  onBulkDelete: () => void
  onCancelBulk: () => void
  onAdd: (source?: KnowledgeItemType, files?: File[]) => void
}

const SOURCE_TYPES: { value: KnowledgeItemType; label: string }[] = [
  { value: 'file', label: '文件' },
  { value: 'note', label: '笔记' },
  { value: 'directory', label: '目录' },
  { value: 'url', label: '网址' },
]

export default function DataSourcePanelHeader({
  readyCount,
  totalCount,
  selectedCount,
  onBulkReindex,
  onBulkDelete,
  onCancelBulk,
  onAdd
}: DataSourcePanelHeaderProps) {
  const [isSourceMenuOpen, setIsSourceMenuOpen] = useState(false)
  const sourceMenuCloseTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  const clearSourceMenuCloseTimer = useCallback(() => {
    if (sourceMenuCloseTimerRef.current) {
      clearTimeout(sourceMenuCloseTimerRef.current)
      sourceMenuCloseTimerRef.current = null
    }
  }, [])

  const openSourceMenu = useCallback(() => {
    clearSourceMenuCloseTimer()
    setIsSourceMenuOpen(true)
  }, [clearSourceMenuCloseTimer])

  const scheduleSourceMenuClose = useCallback(() => {
    clearSourceMenuCloseTimer()
    sourceMenuCloseTimerRef.current = setTimeout(() => {
      setIsSourceMenuOpen(false)
      sourceMenuCloseTimerRef.current = null
    }, 120)
  }, [clearSourceMenuCloseTimer])

  const handleSourceSelect = useCallback(
    (source: KnowledgeItemType) => {
      clearSourceMenuCloseTimer()
      setIsSourceMenuOpen(false)
      onAdd(source)
    },
    [clearSourceMenuCloseTimer, onAdd]
  )

  useEffect(() => clearSourceMenuCloseTimer, [clearSourceMenuCloseTimer])

  if (selectedCount > 0) {
    return (
      <div className="flex min-w-0 items-center justify-between gap-3">
        <div className="flex min-w-0 items-center gap-2">
          <span className="text-sm text-foreground">已选择 {selectedCount} 项</span>
          <button
            type="button"
            className="rounded-md px-2 py-1 text-sm text-foreground-secondary hover:bg-accent"
            onClick={onCancelBulk}>
            取消
          </button>
        </div>
        <div className="flex shrink-0 items-center gap-2">
          <button
            type="button"
            className="flex items-center gap-1.5 rounded-md border border-border px-2.5 py-1.5 text-xs text-foreground-secondary hover:bg-accent"
            onClick={onBulkReindex}>
            <i className="fa-solid fa-rotate text-xs" />
            重新索引
          </button>
          <button
            type="button"
            className="flex items-center gap-1.5 rounded-md border border-border px-2.5 py-1.5 text-xs text-foreground-secondary hover:bg-accent"
            onClick={onBulkDelete}>
            <i className="fa-solid fa-trash-can text-xs" />
            删除
          </button>
        </div>
      </div>
    )
  }

  return (
    <div className="flex min-w-0 items-center justify-end gap-2">
      <div className="flex shrink-0 items-center gap-2">
        {totalCount > 0 ? (
          <span className="text-xs leading-4 text-foreground-muted">
            {readyCount} / {totalCount} 已就绪
          </span>
        ) : null}

        <div className="relative">
          <button
            type="button"
            className="flex min-h-0 items-center gap-1 rounded-lg px-3 py-1.5 text-sm font-medium leading-5 text-foreground-secondary shadow-none hover:bg-accent hover:text-foreground"
            aria-haspopup="menu"
            aria-expanded={isSourceMenuOpen}
            onClick={openSourceMenu}
            onFocus={openSourceMenu}
            onMouseEnter={openSourceMenu}
            onMouseLeave={scheduleSourceMenuClose}>
            <i className="fa-solid fa-plus text-xs" />
            添加数据源
          </button>
          {isSourceMenuOpen ? (
            <div
              className="absolute right-0 z-30 mt-1 w-40 rounded-xl border border-border bg-popover p-1.5 shadow-lg"
              onMouseEnter={openSourceMenu}
              onMouseLeave={scheduleSourceMenuClose}>
              <div className="flex flex-col gap-1" role="menu">
                {SOURCE_TYPES.map((source) => (
                  <button
                    key={source.value}
                    role="menuitem"
                    className="flex h-8 items-center rounded-lg px-2.5 text-sm text-foreground hover:bg-accent"
                    onClick={() => handleSourceSelect(source.value)}>
                    {source.label}
                  </button>
                ))}
              </div>
            </div>
          ) : null}
        </div>
      </div>
    </div>
  )
}
