import type { KnowledgeItem } from '../../../../types/knowledge'
import KnowledgeItemRow from './KnowledgeItemRow'

export interface KnowledgeItemListProps {
  items: KnowledgeItem[]
  allItemsCount: number
  isLoading: boolean
  selectedIds: Set<string>
  onToggleOne: (itemId: string, next: boolean) => void
  onToggleAll: (next: boolean) => void
  onItemClick: (itemId: string) => void
  onDelete: (item: KnowledgeItem) => void | Promise<unknown>
  onPreviewSource: (item: KnowledgeItem) => void | Promise<unknown>
  onReindex: (item: KnowledgeItem) => void | Promise<unknown>
  onViewChunks: (itemId: string) => void
}

export default function KnowledgeItemList({
  items,
  allItemsCount,
  isLoading,
  selectedIds,
  onToggleOne,
  onToggleAll,
  onItemClick,
  onDelete,
  onPreviewSource,
  onReindex,
  onViewChunks
}: KnowledgeItemListProps) {
  if (isLoading) {
    return (
      <div className="flex min-h-0 flex-1 items-center justify-center px-4 text-center text-sm text-foreground-muted">
        <i className="fa-solid fa-circle-notch fa-spin mr-1.5" />
        加载中...
      </div>
    )
  }

  if (allItemsCount === 0) {
    return null
  }

  if (items.length === 0) {
    return (
      <div className="flex min-h-0 flex-1 items-center justify-center px-3 text-center text-sm text-foreground-muted">
        未找到搜索结果
      </div>
    )
  }

  const allSelected = items.every((item) => selectedIds.has(item.id))
  const someSelected = !allSelected && items.some((item) => selectedIds.has(item.id))

  return (
    <div className="min-h-0 flex-1 overflow-y-auto px-3 pt-3 pb-6 [scrollbar-width:none] [&::-webkit-scrollbar]:hidden">
      <table className="w-full table-fixed border-separate border-spacing-x-0 border-spacing-y-1.5 text-sm">
        <colgroup>
          <col className="w-10" />
          <col />
          <col className="w-24" />
          <col className="w-32" />
          <col className="w-32" />
          <col className="w-12" />
        </colgroup>
        <thead className="sticky top-0 z-10 bg-background">
          <tr className="hover:bg-transparent [&>th]:border-b [&>th]:border-border-muted [&>th]:py-0">
            <th className="w-10 px-3">
              <div className="flex h-10 items-center">
                <input
                  type="checkbox"
                  className="h-4 w-4 rounded border-border text-primary focus:ring-primary"
                  aria-label="全选"
                  checked={allSelected}
                  ref={(el) => {
                    if (el) {
                      el.indeterminate = someSelected
                    }
                  }}
                  onChange={(event) => onToggleAll(event.target.checked)}
                />
              </div>
            </th>
            <th className="text-xs font-medium text-foreground-muted">
              <div className="flex h-10 min-w-0 items-center gap-2">
                <span className="size-6 shrink-0" aria-hidden="true" />
                <span>名称</span>
              </div>
            </th>
            <th className="w-24 text-xs font-medium text-foreground-muted">
              <div className="flex h-10 items-center">类型</div>
            </th>
            <th className="w-32 text-xs font-medium text-foreground-muted">
              <div className="flex h-10 items-center">状态</div>
            </th>
            <th className="w-32 text-xs font-medium text-foreground-muted">
              <div className="flex h-10 items-center">更新时间</div>
            </th>
            <th className="w-12" />
          </tr>
        </thead>
        <tbody>
          {items.map((item) => (
            <KnowledgeItemRow
              key={item.id}
              item={item}
              selected={selectedIds.has(item.id)}
              onToggleSelect={(next) => onToggleOne(item.id, next)}
              onClick={() => onItemClick(item.id)}
              onDelete={() => onDelete(item)}
              onPreviewSource={() => onPreviewSource(item)}
              onReindex={() => onReindex(item)}
              onViewChunks={() => onViewChunks(item.id)}
            />
          ))}
        </tbody>
      </table>
    </div>
  )
}
