import type { FocusEvent, MouseEvent } from 'react'
import RecallHistoryList from './RecallHistoryList'
import { useRecallTest } from './RecallTestProvider'

export default function RecallSearchBar() {
  const {
    state: { query, historyItems, isHistoryOpen, isSearching },
    actions: { setQuery, setHistoryOpen, runSearch }
  } = useRecallTest()
  const canSearch = query.trim().length > 0 && !isSearching
  const hasHistory = historyItems.length > 0

  const closeHistoryOnInputBlur = (event: FocusEvent<HTMLInputElement>) => {
    const nextFocusedElement = event.relatedTarget
    if (nextFocusedElement instanceof HTMLElement && nextFocusedElement.closest('[data-recall-history]')) {
      return
    }
    setHistoryOpen(false)
  }

  const keepInputFocus = (event: MouseEvent) => {
    event.preventDefault()
  }

  return (
    <div className="mx-auto flex w-full max-w-3xl items-center gap-2">
      <div className="relative flex flex-1 items-center gap-1.5 rounded-lg border border-border-subtle bg-background px-2.5 py-1.5 transition-all focus-within:border-border-active focus-within:ring-1 focus-within:ring-ring/50">
        <i className="fa-solid fa-magnifying-glass shrink-0 text-xs text-foreground-muted" />
        <input
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          onFocus={() => setHistoryOpen(hasHistory)}
          onBlur={closeHistoryOnInputBlur}
          onKeyDown={(event) => {
            if (event.key === 'Enter' && canSearch) {
              runSearch()
              setHistoryOpen(false)
            }
          }}
          placeholder="输入查询内容测试检索效果..."
          className="h-auto flex-1 border-0 bg-transparent px-0 py-0 text-sm leading-5 text-foreground shadow-none placeholder:text-foreground-muted placeholder:text-sm focus-visible:border-0 focus-visible:ring-0 focus-visible:outline-none"
        />
        {hasHistory ? (
          <button
            type="button"
            tabIndex={-1}
            className={`min-h-0 shrink-0 rounded-none p-0 shadow-none transition-colors hover:bg-transparent hover:text-foreground ${isHistoryOpen ? 'text-primary' : 'text-foreground-muted'}`}
            onMouseDown={keepInputFocus}
            onClick={(event) => {
              event.stopPropagation()
              setHistoryOpen(!isHistoryOpen)
            }}
            aria-label="搜索历史">
            <i className="fa-solid fa-clock-rotate-left text-xs" />
          </button>
        ) : null}

        {hasHistory && isHistoryOpen ? (
          <div
            data-recall-history
            className="absolute top-full right-0 left-0 z-[300] mt-1 max-h-[180px] overflow-y-auto rounded-lg border border-border bg-popover p-1 shadow-lg [scrollbar-width:none] [&::-webkit-scrollbar]:hidden"
            onMouseDown={keepInputFocus}>
            <RecallHistoryList />
          </div>
        ) : null}
      </div>

      <button
        type="button"
        disabled={!canSearch}
        className="flex items-center gap-1.5 rounded-md bg-primary px-3 py-1.5 text-xs font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
        onClick={() => {
          runSearch()
          setHistoryOpen(false)
        }}>
        <i className="fa-solid fa-bolt text-xs" />
        搜索
      </button>
    </div>
  )
}
