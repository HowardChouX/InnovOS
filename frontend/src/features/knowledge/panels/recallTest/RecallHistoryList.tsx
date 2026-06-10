import { useRecallTest } from './RecallTestProvider'

export default function RecallHistoryList() {
  const {
    state: { historyItems },
    actions: { selectHistory, removeHistory, clearHistory }
  } = useRecallTest()

  return (
    <div>
      <div className="mb-0.5 flex items-center justify-between px-2 py-0.5">
        <span className="text-xs leading-4 text-foreground-muted">搜索历史</span>
        <button
          type="button"
          className="h-auto min-h-0 rounded-none p-0 text-xs leading-4 text-foreground-muted shadow-none transition-colors hover:bg-transparent hover:text-accent-danger"
          onClick={clearHistory}>
          清空
        </button>
      </div>

      {historyItems.map((item) => (
        <div
          key={item.id}
          className="group/hist flex w-full cursor-pointer items-center gap-2 rounded-md px-2 py-1 text-left transition-colors hover:bg-accent"
          onClick={() => selectHistory(item)}>
          <button type="button" className="flex min-w-0 flex-1 items-center gap-2 text-left">
            <i className="fa-solid fa-clock-rotate-left shrink-0 text-xs text-foreground-muted" />
            <span className="min-w-0 flex-1 truncate text-sm leading-5 text-foreground">{item.query}</span>
          </button>
          <button
            type="button"
            aria-label="删除"
            className="shrink-0 cursor-default text-foreground-muted opacity-0 transition-all hover:text-accent-danger group-hover/hist:opacity-100"
            onClick={(event) => {
              event.stopPropagation()
              removeHistory(item.id)
            }}>
            <i className="fa-solid fa-xmark text-xs" />
          </button>
        </div>
      ))}
    </div>
  )
}
