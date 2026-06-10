import RecallResultCard from './RecallResultCard'
import { useRecallTest } from './RecallTestProvider'
import { formatRecallPercent, formatRecallScore } from './utils'

const RecallResultSummary = () => {
  const {
    state: { results, duration, topScore, scoreKind }
  } = useRecallTest()

  return (
    <div className="flex items-center justify-between gap-4 border-b border-border-muted px-4 py-3 text-xs leading-4 text-foreground-muted">
      <div className="flex items-center gap-2.5">
        <span className="flex items-center gap-0.5">
          <i className="fa-solid fa-sparkles text-xs" />
          {results.length} 条结果
        </span>
        <span className="flex items-center gap-0.5">
          <i className="fa-solid fa-clock text-xs" />
          {duration}ms
        </span>
        <span>
          {scoreKind === 'ranking'
            ? '仅排名'
            : `最高分 ${results.length === 0 ? formatRecallScore(topScore) : formatRecallPercent(topScore)}`}
        </span>
      </div>
    </div>
  )
}

const RecallResults = () => {
  const {
    state: { results }
  } = useRecallTest()

  return (
    <div className="h-full min-h-0 overflow-y-auto px-6 py-5">
      <div className="mx-auto max-w-3xl overflow-hidden rounded-lg border border-border-subtle bg-card">
        <RecallResultSummary />
        <div className="space-y-2 p-3 pb-6">
          {results.map((item, index) => (
            <RecallResultCard key={item.id} item={item} index={index} />
          ))}
        </div>
      </div>
    </div>
  )
}

const RecallEmptyState = () => {
  return (
    <div className="h-full min-h-0 overflow-y-auto [scrollbar-width:none] [&::-webkit-scrollbar]:hidden">
      <div className="flex h-full flex-col items-center justify-center text-center text-foreground-muted">
        <i className="fa-solid fa-magnifying-glass mb-3 text-4xl opacity-20" />
        <div className="text-sm">输入查询内容测试检索效果</div>
        <div className="mt-1 text-xs">支持向量检索、关键词检索和混合检索</div>
      </div>
    </div>
  )
}

const RecallSearchingState = () => {
  return (
    <div className="flex h-full min-h-full flex-col items-center justify-center py-12 text-center text-foreground-muted">
      <i className="fa-solid fa-circle-notch fa-spin text-xl text-primary" />
      <p className="mt-2 text-sm leading-5">搜索中...</p>
    </div>
  )
}

export default function RecallTestBody() {
  const {
    state: { isSearching, hasSearched }
  } = useRecallTest()

  if (isSearching) {
    return (
      <div className="h-full min-h-0 overflow-y-auto [scrollbar-width:none] [&::-webkit-scrollbar]:hidden">
        <RecallSearchingState />
      </div>
    )
  }

  if (hasSearched) {
    return <RecallResults />
  }

  return <RecallEmptyState />
}
