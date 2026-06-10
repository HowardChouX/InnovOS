import { useState } from 'react'
import type { RecallResultItem } from './types'
import { formatRecallPercent } from './utils'

interface RecallResultCardProps {
  item: RecallResultItem
  index: number
}

export default function RecallResultCard({ item, index }: RecallResultCardProps) {
  const [isExpanded, setIsExpanded] = useState(false)
  const scoreLabel =
    item.scoreKind === 'relevance'
      ? `相关度 ${formatRecallPercent(item.score)}`
      : `排名 #${item.rank}`

  const copyContent = async () => {
    try {
      await navigator.clipboard.writeText(item.plainText)
    } catch {
      // Ignore copy errors
    }
  }

  return (
    <div className="group/chunk rounded-md border border-border-subtle bg-background transition-all hover:border-border-hover">
      <div className="flex items-center gap-2 px-3 py-2">
        <span className="flex size-5 shrink-0 items-center justify-center rounded bg-background-muted text-xs leading-4 text-foreground-muted">
          {index + 1}
        </span>
        <div className="flex min-w-0 flex-1 items-center gap-1">
          <i className="fa-regular fa-file-lines shrink-0 text-xs text-foreground-muted" />
          <span className="truncate text-xs leading-4 text-foreground-muted">{item.sourceName}</span>
          <span className="shrink-0 text-xs leading-3 text-foreground-muted">#{item.chunkIndex}</span>
        </div>
        <div className="flex items-center gap-1.5">
          <span className="w-16 text-right text-xs leading-4 text-foreground-muted tabular-nums">{scoreLabel}</span>
        </div>
        <button
          type="button"
          aria-label="复制"
          className="flex size-5 shrink-0 items-center justify-center rounded p-0 text-foreground-muted opacity-0 shadow-none transition-all hover:bg-accent hover:text-foreground group-hover/chunk:opacity-100"
          onClick={() => void copyContent()}>
          <i className="fa-regular fa-copy text-xs" />
        </button>
        <button
          type="button"
          aria-label={isExpanded ? '收起' : '展开'}
          className="flex size-5 shrink-0 items-center justify-center rounded p-0 text-foreground-muted shadow-none transition-all hover:bg-accent hover:text-foreground"
          onClick={() => setIsExpanded((current) => !current)}>
          <i className={`fa-solid ${isExpanded ? 'fa-chevron-up' : 'fa-chevron-down'} text-xs`} />
        </button>
      </div>
      <div className="overflow-hidden px-3 pb-3">
        <p className={`text-sm leading-relaxed text-foreground-secondary ${isExpanded ? '' : 'line-clamp-2'}`}>
          {item.content}
        </p>
      </div>
    </div>
  )
}
