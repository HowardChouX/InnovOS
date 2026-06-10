import type { KnowledgeItem } from '../../../../types/knowledge'
import type { MouseEvent } from 'react'
import { useState } from 'react'
import { dataSourceTypeDisplayConfig, type DataSourceStatusViewModel } from './utils/models'
import { toKnowledgeItemRowViewModel } from './utils/selectors'

export interface KnowledgeItemRowProps {
  item: KnowledgeItem
  selected: boolean
  onToggleSelect: (next: boolean) => void
  onClick: () => void
  onDelete: () => void | Promise<unknown>
  onPreviewSource: () => void | Promise<unknown>
  onReindex: () => void | Promise<unknown>
  onViewChunks: () => void
}

const KnowledgeItemStatusBadge = ({
  failureReason,
  status
}: {
  failureReason: string | null
  status: DataSourceStatusViewModel
}) => {
  const iconClass =
    status.icon === 'loader'
      ? 'fa-solid fa-spinner fa-spin'
      : status.icon === 'check'
        ? 'fa-solid fa-check'
        : 'fa-solid fa-circle-exclamation'

  const content = (
    <span
      className={`inline-flex shrink-0 items-center gap-1 text-xs ${failureReason ? 'cursor-help' : ''} ${status.textClassName}`}
      tabIndex={failureReason ? 0 : undefined}
      aria-label={failureReason ?? undefined}>
      <i className={`${iconClass} text-[10px]`} />
      <span>{status.label}</span>
    </span>
  )

  if (failureReason) {
    return (
      <div className="group relative">
        {content}
        <div className="pointer-events-none absolute bottom-full left-0 z-40 mb-1 hidden max-w-72 rounded-md border border-border bg-popover px-2.5 py-1.5 text-xs text-foreground shadow-lg group-hover:block">
          {failureReason}
        </div>
      </div>
    )
  }

  return content
}

const KnowledgeItemRowMoreMenu = ({
  canReindex,
  canViewChunks,
  onDelete,
  onPreviewSource,
  onReindex,
  onViewChunks
}: {
  canReindex: boolean
  canViewChunks: boolean
  onDelete: () => void | Promise<unknown>
  onPreviewSource: () => void | Promise<unknown>
  onReindex: () => void | Promise<unknown>
  onViewChunks: () => void
}) => {
  const [isOpen, setIsOpen] = useState(false)

  const handleAction = (action: () => void | Promise<unknown>) => (event: MouseEvent<HTMLButtonElement>) => {
    event.stopPropagation()
    setIsOpen(false)
    void Promise.resolve(action()).catch(() => {})
  }

  return (
    <div className="relative">
      <button
        type="button"
        aria-label="更多"
        className={`flex h-7 w-7 items-center justify-center rounded-md text-foreground-muted transition-opacity hover:bg-accent hover:text-foreground ${isOpen ? 'opacity-100' : 'opacity-0 group-hover/row:opacity-100'}`}
        onClick={(event) => {
          event.stopPropagation()
          setIsOpen(!isOpen)
        }}>
        <i className="fa-solid fa-ellipsis text-xs" />
      </button>
      {isOpen ? (
        <div
          className="absolute right-0 z-30 mt-1 w-max min-w-[140px] max-w-56 rounded-lg border border-border bg-popover p-1 shadow-lg"
          onClick={(event) => event.stopPropagation()}>
          <div className="flex flex-col gap-0.5">
            <button
              type="button"
              className="flex items-center gap-2 rounded-md px-2 py-1.5 text-sm text-foreground hover:bg-accent"
              onClick={handleAction(onPreviewSource)}>
              <i className="fa-solid fa-book-open text-xs" />
              预览源
            </button>
            {canViewChunks ? (
              <button
                type="button"
                className="flex items-center gap-2 rounded-md px-2 py-1.5 text-sm text-foreground hover:bg-accent"
                onClick={handleAction(onViewChunks)}>
                <i className="fa-solid fa-eye text-xs" />
                查看分块
              </button>
            ) : null}
            {canReindex ? (
              <button
                type="button"
                className="flex items-center gap-2 rounded-md px-2 py-1.5 text-sm text-foreground hover:bg-accent"
                onClick={handleAction(onReindex)}>
                <i className="fa-solid fa-rotate text-xs" />
                重新索引
              </button>
            ) : null}
            <button
              type="button"
              className="flex items-center gap-2 rounded-md px-2 py-1.5 text-sm text-accent-danger hover-danger-subtle"
              onClick={handleAction(onDelete)}>
              <i className="fa-solid fa-trash-can text-xs" />
              删除
            </button>
          </div>
        </div>
      ) : null}
    </div>
  )
}

export default function KnowledgeItemRow({
  item,
  selected,
  onToggleSelect,
  onClick,
  onDelete,
  onPreviewSource,
  onReindex,
  onViewChunks
}: KnowledgeItemRowProps) {
  const { icon, metaParts, status, suffix, title } = toKnowledgeItemRowViewModel(item)
  const failureReason = item.status === 'failed' ? item.error : null
  const canReindex = item.status === 'completed' || item.status === 'failed'
  const canViewChunks = item.status === 'completed'
  const typeLabel = dataSourceTypeDisplayConfig[item.type].filterLabel
  const updatedAt = new Date(item.updatedAt).toLocaleDateString()
  const fullTitle = 'source' in item.data ? item.data.source : title

  const iconMap: Record<string, string> = {
    file: 'fa-regular fa-file-lines',
    note: 'fa-regular fa-note-sticky',
    directory: 'fa-regular fa-folder',
    url: 'fa-solid fa-link'
  }

  return (
    <tr
      data-state={selected ? 'selected' : undefined}
      onClick={canViewChunks ? onClick : undefined}
      className={`group/row transition-colors ${canViewChunks ? 'cursor-pointer' : ''} hover:bg-transparent data-[state=selected]:bg-transparent [&>td:first-child]:rounded-l-lg [&>td:last-child]:rounded-r-lg [&>td]:transition-colors ${selected ? '[&>td]:bg-accent' : canViewChunks ? '[&:hover>td]:bg-accent/40' : ''}`}>
      <td className="w-10 px-3" onClick={(event) => event.stopPropagation()}>
        <input
          type="checkbox"
          className="h-4 w-4 rounded border-border text-primary focus:ring-primary"
          aria-label="选择行"
          checked={selected}
          onChange={(event) => onToggleSelect(event.target.checked)}
        />
      </td>
      <td className="min-w-0 py-3">
        <div className="flex min-w-0 items-start gap-2">
          <span className="flex size-6 shrink-0 items-center justify-center rounded bg-background-muted">
            <i className={`${iconMap[item.type] || 'fa-regular fa-file'} text-xs ${icon.iconClassName}`} />
          </span>
          <div className="min-w-0 flex-1">
            <div className="flex min-w-0 items-center gap-1.5">
              <span className="min-w-0 truncate text-sm text-foreground" title={fullTitle}>
                {title}
              </span>
              {suffix ? <span className="shrink-0 text-xs uppercase text-foreground-muted">{suffix}</span> : null}
            </div>
            {metaParts.length > 0 ? (
              <div className="mt-0.5 flex min-w-0 flex-wrap items-center gap-x-1.5 gap-y-0.5 text-xs leading-4 text-foreground-muted">
                {metaParts.map((part, index) => (
                  <span key={`${part}-${index}`} className="inline-flex min-w-0 items-center gap-1.5">
                    {index > 0 ? <span aria-hidden="true">·</span> : null}
                    <span className="truncate">{part}</span>
                  </span>
                ))}
              </div>
            ) : null}
          </div>
        </div>
      </td>
      <td className="w-24 text-xs text-foreground-secondary">{typeLabel}</td>
      <td className="w-32">
        <KnowledgeItemStatusBadge status={status} failureReason={failureReason} />
      </td>
      <td className="w-32 text-xs text-foreground-muted">{updatedAt}</td>
      <td className="w-12 px-2" onClick={(event) => event.stopPropagation()}>
        <KnowledgeItemRowMoreMenu
          canReindex={canReindex}
          canViewChunks={canViewChunks}
          onDelete={onDelete}
          onPreviewSource={onPreviewSource}
          onReindex={onReindex}
          onViewChunks={onViewChunks}
        />
      </td>
    </tr>
  )
}
