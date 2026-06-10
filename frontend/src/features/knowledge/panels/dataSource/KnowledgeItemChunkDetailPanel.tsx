import type { KnowledgeItem, KnowledgeItemChunk } from '../../../../types/knowledge'
import { knowledgeApi } from '../../../../api/knowledge'
import type { ReactNode } from 'react'
import { useEffect, useRef, useState } from 'react'
import { toKnowledgeItemRowViewModel } from './utils/selectors'
import { dataSourceTypeDisplayConfig } from './utils/models'

interface KnowledgeItemChunkDetailPanelProps {
  baseId: string
  itemId: string
  item?: KnowledgeItem
  onBack: () => void
}

const KnowledgeItemChunkActionButton = ({
  label,
  className,
  children,
  disabled,
  onClick
}: {
  label: string
  className?: string
  children: ReactNode
  disabled?: boolean
  onClick?: () => void
}) => {
  const handleClick = (event: React.MouseEvent<HTMLButtonElement>) => {
    event.stopPropagation()
    onClick?.()
  }

  return (
    <button
      type="button"
      aria-label={label}
      className={`flex size-5 items-center justify-center rounded p-0 text-foreground-muted shadow-none transition-colors hover:bg-accent hover:text-foreground ${className ?? ''}`}
      disabled={disabled}
      onClick={handleClick}>
      {children}
    </button>
  )
}

const KnowledgeItemChunkCard = ({
  chunk,
  isDeleting,
  onDelete
}: {
  chunk: KnowledgeItemChunk
  isDeleting: boolean
  onDelete: (chunk: KnowledgeItemChunk) => void
}) => {
  return (
    <div className="group/ck rounded-lg border border-border-subtle transition-all hover:border-border-hover">
      <div className="flex items-center gap-2 px-3 py-2">
        <span className="flex size-5 shrink-0 items-center justify-center rounded bg-accent text-xs leading-4 text-foreground-muted">
          {chunk.metadata.chunkIndex}
        </span>
        <span className="flex-1 text-xs leading-4 text-foreground-muted">
          {chunk.metadata.tokenCount} tokens
        </span>
        <div className="flex items-center gap-0.5 opacity-0 transition-all group-hover/ck:opacity-100">
          <KnowledgeItemChunkActionButton
            label="删除"
            className="hover-danger-subtle hover:text-accent-danger"
            disabled={isDeleting}
            onClick={() => onDelete(chunk)}>
            <i className="fa-solid fa-trash-can text-xs" />
          </KnowledgeItemChunkActionButton>
        </div>
      </div>
      <div className="px-3 pb-3">
        <p className="line-clamp-2 text-sm leading-relaxed text-foreground-secondary">{chunk.content}</p>
      </div>
    </div>
  )
}

const KnowledgeItemChunkState = ({ children }: { children: ReactNode }) => (
  <div className="flex min-h-full items-center justify-center px-4 py-10 text-center text-sm leading-5 text-foreground-muted">
    {children}
  </div>
)

export default function KnowledgeItemChunkDetailPanel({
  baseId,
  itemId,
  item: initialItem,
  onBack
}: KnowledgeItemChunkDetailPanelProps) {
  const [fetchedItem, setFetchedItem] = useState<KnowledgeItem | null>(null)
  const [isItemLoading, setIsItemLoading] = useState(true)
  const [itemError, setItemError] = useState<Error | null>(null)
  const [chunks, setChunks] = useState<KnowledgeItemChunk[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<Error | null>(null)
  const [deletingChunkId, setDeletingChunkId] = useState<string | null>(null)
  const [pendingDeleteChunk, setPendingDeleteChunk] = useState<KnowledgeItemChunk | null>(null)
  const keepDeleteDialogOpenRef = useRef(false)
  const item = fetchedItem ?? initialItem

  const viewModel = item ? toKnowledgeItemRowViewModel(item) : null
  const iconMap: Record<string, string> = {
    file: 'fa-regular fa-file-lines',
    note: 'fa-regular fa-note-sticky',
    directory: 'fa-regular fa-folder',
    url: 'fa-solid fa-link'
  }
  const typeMeta = item && viewModel ? viewModel.suffix || dataSourceTypeDisplayConfig[item.type].filterLabel : ''
  const chunksCountMeta = `${chunks.length} 个分块`
  const metaParts = [typeMeta, chunksCountMeta].filter((part): part is string => Boolean(part))

  useEffect(() => {
    let isActive = true

    const loadItem = async () => {
      try {
        const res = await knowledgeApi.getItem(itemId)
        if (isActive) setFetchedItem(res.data)
      } catch (err) {
        if (isActive) setItemError(err instanceof Error ? err : new Error(String(err)))
      } finally {
        if (isActive) setIsItemLoading(false)
      }
    }

    const loadChunks = async () => {
      setIsLoading(true)
      setError(null)

      try {
        // Note: InnovOS API may not have listItemChunks endpoint yet.
        // Using a placeholder approach - in production this should call knowledgeApi.listItemChunks(baseId, itemId)
        // Note: InnovOS API may not have listItemChunks endpoint yet.
        await knowledgeApi.search({ q: '', base_id: baseId, limit: 100 })
        if (isActive) {
          setChunks([])
        }
      } catch (chunkError) {
        if (isActive) {
          setChunks([])
          setError(chunkError instanceof Error ? chunkError : new Error(String(chunkError)))
        }
      } finally {
        if (isActive) {
          setIsLoading(false)
        }
      }
    }

    void loadItem()
    void loadChunks()

    return () => {
      isActive = false
    }
  }, [baseId, itemId])

  const handleRequestDeleteChunk = (chunk: KnowledgeItemChunk) => {
    keepDeleteDialogOpenRef.current = false
    setPendingDeleteChunk(chunk)
  }

  const handleConfirmDeleteChunk = async () => {
    const chunk = pendingDeleteChunk
    if (!chunk) {
      return
    }

    setDeletingChunkId(chunk.id)
    setError(null)
    keepDeleteDialogOpenRef.current = false

    try {
      // Note: InnovOS API may not have deleteItemChunk endpoint yet.
      // In production this should call knowledgeApi.deleteItemChunk(baseId, chunk.itemId, chunk.id)
      setChunks((currentChunks) => currentChunks.filter((currentChunk) => currentChunk.id !== chunk.id))
      setPendingDeleteChunk(null)
    } catch (chunkError) {
      setError(chunkError instanceof Error ? chunkError : new Error(String(chunkError)))
      keepDeleteDialogOpenRef.current = true
    } finally {
      setDeletingChunkId(null)
    }
  }

  return (
    <div className="flex h-full min-h-0 flex-col">
      <div className="flex shrink-0 items-center gap-2 border-b border-border-muted px-3 py-2">
        <button
          type="button"
          aria-label="返回"
          className="flex size-5 items-center justify-center rounded p-0 text-foreground-muted shadow-none transition-colors hover:bg-accent hover:text-foreground"
          onClick={onBack}>
          <i className="fa-solid fa-arrow-left text-xs" />
        </button>
        {viewModel && item ? (
          <div
            className={`flex size-6 shrink-0 items-center justify-center rounded bg-accent ${viewModel.icon.iconClassName}`}>
            <i className={`${iconMap[item.type] || 'fa-regular fa-file'} text-xs`} />
          </div>
        ) : null}
        <div className="min-w-0 flex-1">
          <span className="block truncate text-sm leading-5 text-foreground">
            {viewModel?.title ?? '加载中...'}
          </span>
          <div className="flex items-center gap-2 text-xs leading-4 text-foreground-muted">
            {metaParts.map((part) => (
              <span key={part} className={viewModel && part === typeMeta && viewModel.suffix ? 'uppercase' : undefined}>
                {part}
              </span>
            ))}
          </div>
        </div>
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto px-4 py-3 [scrollbar-width:none] [&::-webkit-scrollbar]:hidden">
        {isItemLoading || isLoading ? <KnowledgeItemChunkState>加载中...</KnowledgeItemChunkState> : null}
        {!isItemLoading && itemError ? <KnowledgeItemChunkState>{itemError.message}</KnowledgeItemChunkState> : null}
        {!isItemLoading && !isLoading && !itemError && error ? (
          <KnowledgeItemChunkState>{error.message}</KnowledgeItemChunkState>
        ) : null}
        {!isItemLoading && !isLoading && !itemError && !error && chunks.length === 0 ? (
          <KnowledgeItemChunkState>暂无分块数据</KnowledgeItemChunkState>
        ) : null}
        {!isItemLoading && !isLoading && !itemError && chunks.length > 0 ? (
          <div className="space-y-2">
            {chunks.map((chunk) => (
              <KnowledgeItemChunkCard
                key={chunk.id}
                chunk={chunk}
                isDeleting={deletingChunkId === chunk.id}
                onDelete={handleRequestDeleteChunk}
              />
            ))}
          </div>
        ) : null}
      </div>

      {/* Inline Confirm Dialog for chunk delete */}
      {pendingDeleteChunk ? (
        <div className="fixed inset-0 z-[9999] flex items-center justify-center bg-black/50" onClick={() => {
          if (keepDeleteDialogOpenRef.current) {
            keepDeleteDialogOpenRef.current = false
            return
          }
          setPendingDeleteChunk(null)
        }}>
          <div className="w-[360px] rounded-xl border border-border bg-card p-5" onClick={e => e.stopPropagation()}>
            <div className="mb-3 text-base font-semibold text-foreground">删除分块</div>
            <div className="mb-4 text-sm text-foreground-secondary">确定要删除这个分块吗？此操作不可撤销。</div>
            <div className="flex justify-end gap-2">
              <button
                onClick={() => setPendingDeleteChunk(null)}
                className="rounded-md border border-border px-3.5 py-1.5 text-xs text-foreground-secondary hover:bg-accent">
                取消
              </button>
              <button
                onClick={handleConfirmDeleteChunk}
                disabled={!!deletingChunkId}
                className="rounded-md bg-[var(--accent-red)] px-3.5 py-1.5 text-xs text-white hover:opacity-90 disabled:opacity-50">
                {deletingChunkId ? '删除中...' : '删除'}
              </button>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  )
}
