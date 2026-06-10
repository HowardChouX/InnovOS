import type { KnowledgeItem, KnowledgeItemType } from '../../../../types/knowledge'
import type { ChangeEvent } from 'react'
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import KnowledgePanelShell from '../../components/KnowledgePanelShell'
import DataSourcePanelHeader from './DataSourcePanelHeader'
import KnowledgeItemList from './KnowledgeItemList'
import { getItemTitle, getReadyCount } from './utils/selectors'

export interface DataSourcePanelProps {
  items: KnowledgeItem[]
  isLoading: boolean
  searchQuery?: string
  onAdd: (source?: KnowledgeItemType, files?: File[]) => void
  onItemClick?: (itemId: string) => void
  onDelete: (item: KnowledgeItem) => void | Promise<unknown>
  onReindex: (item: KnowledgeItem) => void | Promise<unknown>
}

const matchesSearch = (item: KnowledgeItem, query: string) => {
  if (!query) {
    return true
  }
  return getItemTitle(item).toLowerCase().includes(query.toLowerCase())
}

const DataSourceEmptyState = ({ onAddSource }: { onAddSource: (source: KnowledgeItemType) => void }) => {
  const sourceTypes: { value: KnowledgeItemType; label: string; icon: string }[] = [
    { value: 'file', label: '文件', icon: 'fa-regular fa-file-lines' },
    { value: 'note', label: '笔记', icon: 'fa-regular fa-note-sticky' },
    { value: 'directory', label: '目录', icon: 'fa-regular fa-folder' },
    { value: 'url', label: '网址', icon: 'fa-solid fa-link' },
  ]

  return (
    <div className="flex min-h-0 flex-1 items-center justify-center px-6 py-12 text-center">
      <div className="flex max-w-4xl flex-col items-center">
        <h3 className="text-lg font-semibold leading-7 text-foreground">暂无数据源</h3>
        <p className="mt-2 text-sm leading-5 text-foreground-muted">点击上方按钮添加数据源</p>
        <div className="mt-7 flex flex-wrap justify-center gap-2.5">
          {sourceTypes.map((source) => {
            return (
              <button
                key={source.value}
                type="button"
                className="flex h-9 w-24 items-center justify-center gap-1.5 rounded-lg border border-border px-3 font-medium text-sm hover:bg-accent"
                onClick={() => onAddSource(source.value)}>
                <i className={`${source.icon} text-xs text-foreground-secondary`} />
                {source.label}
              </button>
            )
          })}
        </div>
      </div>
    </div>
  )
}

export default function DataSourcePanel({
  items,
  isLoading,
  searchQuery = '',
  onAdd,
  onItemClick,
  onDelete,
  onReindex
}: DataSourcePanelProps) {
  const fileInputRef = useRef<HTMLInputElement>(null)
  const [selectedIds, setSelectedIds] = useState<Set<string>>(() => new Set())
  const [pendingDeleteItem, setPendingDeleteItem] = useState<KnowledgeItem | null>(null)
  const [isBulkDeleteOpen, setIsBulkDeleteOpen] = useState(false)
  const [errorMessage, setErrorMessage] = useState<string | null>(null)

  const visibleItems = useMemo(() => items.filter((item) => matchesSearch(item, searchQuery)), [items, searchQuery])

  useEffect(() => {
    setSelectedIds((prev) => {
      const visibleItemIds = new Set(visibleItems.map((item) => item.id))
      const next = new Set([...prev].filter((itemId) => visibleItemIds.has(itemId)))
      return next.size === prev.size ? prev : next
    })
  }, [visibleItems])

  const readyCount = useMemo(() => getReadyCount(items), [items])

  const handleItemClick = (itemId: string) => onItemClick?.(itemId)

  const handleToggleOne = useCallback((itemId: string, next: boolean) => {
    setSelectedIds((prev) => {
      const updated = new Set(prev)
      if (next) {
        updated.add(itemId)
      } else {
        updated.delete(itemId)
      }
      return updated
    })
  }, [])

  const handleToggleAll = useCallback(
    (next: boolean) => {
      setSelectedIds(next ? new Set(visibleItems.map((item) => item.id)) : new Set())
    },
    [visibleItems]
  )

  const handleCancelBulk = useCallback(() => {
    setSelectedIds(new Set())
  }, [])

  const handleBulkReindex = useCallback(async () => {
    const targets = visibleItems.filter((item) => selectedIds.has(item.id))
    try {
      await Promise.all(targets.map((item) => onReindex(item)))
    } catch (error) {
      setErrorMessage(`重新索引失败: ${error instanceof Error ? error.message : String(error)}`)
      return
    }
    setSelectedIds(new Set())
  }, [onReindex, selectedIds, visibleItems])

  const handleBulkDelete = useCallback(async () => {
    const targets = visibleItems.filter((item) => selectedIds.has(item.id))
    try {
      await Promise.all(targets.map((item) => onDelete(item)))
    } catch (error) {
      setErrorMessage(`删除失败: ${error instanceof Error ? error.message : String(error)}`)
      return
    }
    setSelectedIds(new Set())
    setIsBulkDeleteOpen(false)
  }, [onDelete, selectedIds, visibleItems])

  const handleConfirmDelete = async () => {
    if (!pendingDeleteItem) {
      return
    }
    try {
      await onDelete(pendingDeleteItem)
    } catch (error) {
      setErrorMessage(`删除失败: ${error instanceof Error ? error.message : String(error)}`)
      return
    }
    setPendingDeleteItem(null)
  }

  const handleFileSelect = (event: ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(event.target.files ?? [])
    event.target.value = ''
    if (files.length > 0) {
      onAdd('file', files)
    }
  }

  const openFilePicker = useCallback(() => {
    fileInputRef.current?.click()
  }, [])

  const handleAddSource = useCallback(
    (source?: KnowledgeItemType, files?: File[]) => {
      if (source === 'file' && !files?.length) {
        openFilePicker()
        return
      }
      if (files?.length) {
        onAdd(source, files)
        return
      }
      onAdd(source)
    },
    [onAdd, openFilePicker]
  )

  const handlePreviewSource = async (item: KnowledgeItem) => {
    const source = item.data.source?.trim()
    if (!source) {
      setErrorMessage('无法预览此数据源')
      return
    }
    try {
      if (item.type === 'url' || item.type === 'note') {
        window.open(source, '_blank')
        return
      }
      // For file/directory types, we can't open local paths in a web app
      setErrorMessage('本地文件预览需要在桌面应用中打开')
    } catch {
      setErrorMessage('预览失败')
    }
  }

  return (
    <KnowledgePanelShell
      headerClassName="shrink-0 px-3 pt-4"
      header={
        <div className="border-b border-border-muted pb-3">
          <DataSourcePanelHeader
            readyCount={readyCount}
            totalCount={items.length}
            selectedCount={selectedIds.size}
            onBulkReindex={handleBulkReindex}
            onBulkDelete={() => setIsBulkDeleteOpen(true)}
            onCancelBulk={handleCancelBulk}
            onAdd={handleAddSource}
          />
        </div>
      }>
      <input
        ref={fileInputRef}
        type="file"
        multiple
        className="sr-only"
        tabIndex={-1}
        aria-hidden="true"
        onChange={handleFileSelect}
      />
      <div className="flex min-h-0 flex-1 flex-col">
        {!isLoading && items.length === 0 ? (
          <DataSourceEmptyState onAddSource={handleAddSource} />
        ) : (
          <KnowledgeItemList
            items={visibleItems}
            allItemsCount={items.length}
            isLoading={isLoading}
            selectedIds={selectedIds}
            onToggleOne={handleToggleOne}
            onToggleAll={handleToggleAll}
            onItemClick={handleItemClick}
            onDelete={setPendingDeleteItem}
            onPreviewSource={handlePreviewSource}
            onReindex={onReindex}
            onViewChunks={handleItemClick}
          />
        )}
      </div>

      {/* Error Toast */}
      {errorMessage ? (
        <div className="fixed bottom-4 right-4 z-[9999] rounded-lg badge-danger px-4 py-2 text-sm">
          {errorMessage}
          <button onClick={() => setErrorMessage(null)} className="ml-2 text-accent-danger hover:opacity-80">
            <i className="fa-solid fa-xmark" />
          </button>
        </div>
      ) : null}

      {/* Single Item Delete Dialog */}
      {pendingDeleteItem ? (
        <div className="fixed inset-0 z-[9999] flex items-center justify-center bg-black/50" onClick={() => setPendingDeleteItem(null)}>
          <div className="w-[360px] rounded-xl border border-border bg-card p-5" onClick={e => e.stopPropagation()}>
            <div className="mb-3 text-base font-semibold text-foreground">删除数据源</div>
            <div className="mb-4 text-sm text-foreground-secondary">确定要删除这个数据源吗？此操作不可撤销。</div>
            <div className="flex justify-end gap-2">
              <button
                onClick={() => setPendingDeleteItem(null)}
                className="rounded-md border border-border px-3.5 py-1.5 text-xs text-foreground-secondary hover:bg-accent">
                取消
              </button>
              <button
                onClick={handleConfirmDelete}
                className="rounded-md bg-[var(--accent-red)] px-3.5 py-1.5 text-xs text-white hover:opacity-90">
                删除
              </button>
            </div>
          </div>
        </div>
      ) : null}

      {/* Bulk Delete Dialog */}
      {isBulkDeleteOpen ? (
        <div className="fixed inset-0 z-[9999] flex items-center justify-center bg-black/50" onClick={() => setIsBulkDeleteOpen(false)}>
          <div className="w-[360px] rounded-xl border border-border bg-card p-5" onClick={e => e.stopPropagation()}>
            <div className="mb-3 text-base font-semibold text-foreground">批量删除</div>
            <div className="mb-4 text-sm text-foreground-secondary">确定要删除选中的 {selectedIds.size} 个数据源吗？此操作不可撤销。</div>
            <div className="flex justify-end gap-2">
              <button
                onClick={() => setIsBulkDeleteOpen(false)}
                className="rounded-md border border-border px-3.5 py-1.5 text-xs text-foreground-secondary hover:bg-accent">
                取消
              </button>
              <button
                onClick={handleBulkDelete}
                className="rounded-md bg-[var(--accent-red)] px-3.5 py-1.5 text-xs text-white hover:opacity-90">
                删除
              </button>
            </div>
          </div>
        </div>
      ) : null}
    </KnowledgePanelShell>
  )
}
