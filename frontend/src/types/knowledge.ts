export type KnowledgeItemType = 'file' | 'url' | 'note' | 'directory'
export type KnowledgeItemStatus = 'idle' | 'preparing' | 'processing' | 'reading' | 'embedding' | 'completed' | 'failed' | 'deleting'
export type KnowledgeSearchMode = 'default' | 'bm25' | 'hybrid'
export type KnowledgeBaseStatus = 'completed' | 'failed'

export interface KnowledgeBase {
  id: string
  name: string
  groupId: string | null
  dimensions: number | null
  embeddingModelId: string | null
  status: KnowledgeBaseStatus
  error: string | null
  rerankModelId: string | null
  fileProcessorId: string | null
  chunkSize: number
  chunkOverlap: number
  threshold: number | null
  documentCount: number | null
  searchMode: KnowledgeSearchMode
  hybridAlpha: number | null
  createdAt: string
  updatedAt: string
  itemCount?: number
}

export interface KnowledgeBaseListItem extends KnowledgeBase {
  itemCount: number
}

export interface FileItemData {
  source: string
  fileEntryId?: string
}

export interface UrlItemData {
  source: string
  url: string
}

export interface NoteItemData {
  source: string
  content: string
  sourceUrl?: string
}

export interface DirectoryItemData {
  source: string
  path: string
}

export type KnowledgeItemData = FileItemData | UrlItemData | NoteItemData | DirectoryItemData

export interface KnowledgeItem {
  id: string
  baseId: string
  groupId: string | null
  type: KnowledgeItemType
  data: KnowledgeItemData
  status: KnowledgeItemStatus
  error: string | null
  createdAt: string
  updatedAt: string
}

export interface KnowledgeChunkMetadata {
  itemId: string
  itemType: KnowledgeItemType
  source: string
  chunkIndex: number
  tokenCount: number
}

export interface KnowledgeSearchResult {
  pageContent: string
  score: number
  scoreKind: 'relevance' | 'ranking'
  rank: number
  metadata: KnowledgeChunkMetadata
  itemId?: string
  chunkId: string
}

export interface KnowledgeItemChunk {
  id: string
  itemId: string
  content: string
  metadata: KnowledgeChunkMetadata
}

export interface KnowledgeGroup {
  id: string
  name: string
  userId?: number
  createdAt?: string
  updatedAt?: string
}

export interface OffsetPaginationResponse<T> {
  items: T[]
  total: number
  page: number
}

export type KnowledgeTabKey = 'file' | 'note' | 'directory' | 'url'
