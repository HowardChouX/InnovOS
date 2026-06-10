import type { ReactNode } from 'react'
import { createContext, use, useEffect, useRef, useState } from 'react'
import { knowledgeApi } from '../../../../api/knowledge'
import type { RecallResultItem, RecallTestContextValue } from './types'
import { mapRecallResult, prependHistoryQuery } from './utils'

const RecallTestContext = createContext<RecallTestContextValue | null>(null)

export const useRecallTest = () => {
  const context = use(RecallTestContext)
  if (!context) {
    throw new Error('RecallTest components must be used within RecallTestProvider')
  }
  return context
}

interface RecallTestProviderProps {
  baseId: string
  children: ReactNode
}

const HISTORY_STORAGE_KEY = 'knowledge.recall.search_queries'

const loadHistoryQueries = (): Record<string, string[]> => {
  try {
    const raw = localStorage.getItem(HISTORY_STORAGE_KEY)
    return raw ? JSON.parse(raw) : {}
  } catch {
    return {}
  }
}

const saveHistoryQueries = (queries: Record<string, string[]>) => {
  localStorage.setItem(HISTORY_STORAGE_KEY, JSON.stringify(queries))
}

export default function RecallTestProvider({ baseId, children }: RecallTestProviderProps) {
  const latestSearchIdRef = useRef(0)
  const [query, setQuery] = useState('')
  const [historyQueriesByBaseId, setHistoryQueriesByBaseId] = useState<Record<string, string[]>>(loadHistoryQueries)
  const [isHistoryOpen, setIsHistoryOpen] = useState(false)
  const [hasSearched, setHasSearched] = useState(false)
  const [results, setResults] = useState<RecallResultItem[]>([])
  const [duration, setDuration] = useState(0)
  const [isSearching, setIsSearching] = useState(false)
  const [errorMessage, setErrorMessage] = useState<string | null>(null)

  useEffect(() => {
    latestSearchIdRef.current += 1
    setQuery('')
    setIsHistoryOpen(false)
    setHasSearched(false)
    setResults([])
    setDuration(0)
    setIsSearching(false)
    setErrorMessage(null)

    return () => {
      latestSearchIdRef.current += 1
    }
  }, [baseId])

  const historyQueries = historyQueriesByBaseId[baseId] ?? []
  const historyItems = historyQueries.map((query) => ({ id: query, query }))
  const scoreKind = results[0]?.scoreKind ?? null
  const topScore = scoreKind === 'relevance' ? results.reduce((score, item) => Math.max(score, item.score), 0) : 0

  const runSearch = async () => {
    const trimmedQuery = query.trim()

    if (trimmedQuery.length === 0) {
      return
    }

    const currentHistoryQueries = historyQueriesByBaseId[baseId] ?? []
    const nextHistory = prependHistoryQuery(currentHistoryQueries, trimmedQuery)
    const nextHistoryByBaseId = {
      ...historyQueriesByBaseId,
      [baseId]: nextHistory
    }
    setHistoryQueriesByBaseId(nextHistoryByBaseId)
    saveHistoryQueries(nextHistoryByBaseId)

    const searchId = latestSearchIdRef.current + 1
    latestSearchIdRef.current = searchId
    const searchBaseId = baseId
    const isCurrentSearch = () => latestSearchIdRef.current === searchId

    setIsSearching(true)
    setResults([])
    setErrorMessage(null)
    const startTime = performance.now()

    try {
      const searchResults = await knowledgeApi.search({ q: trimmedQuery, base_id: searchBaseId, limit: 10 })
      if (!isCurrentSearch()) {
        return
      }
      const mapped = (searchResults.data || []).map(mapRecallResult)
      setResults(mapped)
    } catch (error) {
      if (!isCurrentSearch()) {
        return
      }
      setErrorMessage(`搜索失败: ${error instanceof Error ? error.message : String(error)}`)
      setResults([])
    }

    if (!isCurrentSearch()) {
      return
    }

    setDuration(Math.round(performance.now() - startTime))
    setIsSearching(false)
    setHasSearched(true)
  }

  const value: RecallTestContextValue = {
    state: {
      query,
      historyItems,
      isHistoryOpen,
      isSearching,
      hasSearched,
      results,
      duration,
      topScore,
      scoreKind
    },
    actions: {
      setQuery,
      setHistoryOpen: setIsHistoryOpen,
      runSearch,
      selectHistory: (item) => {
        setQuery(item.query)
        setIsHistoryOpen(false)
      },
      removeHistory: (historyId) => {
        const next = {
          ...historyQueriesByBaseId,
          [baseId]: historyQueries.filter((item) => item !== historyId)
        }
        setHistoryQueriesByBaseId(next)
        saveHistoryQueries(next)
      },
      clearHistory: () => {
        const next = {
          ...historyQueriesByBaseId,
          [baseId]: []
        }
        setHistoryQueriesByBaseId(next)
        saveHistoryQueries(next)
      }
    },
    meta: { baseId }
  }

  return (
    <RecallTestContext value={value}>
      {children}
      {errorMessage ? (
        <div className="fixed bottom-4 right-4 z-[9999] rounded-lg badge-danger px-4 py-2 text-sm">
          {errorMessage}
          <button onClick={() => setErrorMessage(null)} className="ml-2 text-accent-danger hover:opacity-80">
            <i className="fa-solid fa-xmark" />
          </button>
        </div>
      ) : null}
    </RecallTestContext>
  )
}
