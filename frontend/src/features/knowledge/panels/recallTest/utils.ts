import type { KnowledgeSearchResult } from '../../../../types/knowledge'
import type { RecallResultItem } from './types'

const MAX_HISTORY_QUERY_COUNT = 5

export const prependHistoryQuery = (queries: string[], query: string) => {
  return [query, ...queries.filter((item) => item !== query)].slice(0, MAX_HISTORY_QUERY_COUNT)
}

export const formatRecallScore = (score: number) => score.toFixed(2)
export const formatRecallPercent = (score: number) => `${Math.round(Math.max(0, Math.min(score, 1)) * 100)}%`

export const mapRecallResult = (result: KnowledgeSearchResult): RecallResultItem => {
  const meta = result.metadata || {} as any;
  return {
    id: result.chunkId || '',
    sourceName: meta.source || '',
    chunkIndex: meta.chunkIndex ?? 0,
    tokenCount: meta.tokenCount ?? 0,
    score: result.score ?? 0,
    scoreKind: result.scoreKind || 'relevance',
    rank: result.rank ?? 0,
    content: result.pageContent || '',
    plainText: result.pageContent || ''
  }
}
