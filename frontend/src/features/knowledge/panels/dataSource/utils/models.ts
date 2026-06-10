import type { KnowledgeItemType } from '../../../../../types/knowledge'

export type DataSourceStatus = 'completed' | 'processing' | 'failed'
export type DataSourceStatusIcon = 'check' | 'loader' | 'alert'

export interface DataSourceStatusViewModel {
  kind: DataSourceStatus
  label: string
  textClassName: string
  icon: DataSourceStatusIcon
}

export interface DataSourceIconMeta {
  iconClassName: string
}

export interface KnowledgeItemRowViewModel {
  title: string
  suffix: string
  metaParts: string[]
  icon: DataSourceIconMeta
  status: DataSourceStatusViewModel
}

export interface DataSourceTypeDisplayConfig {
  filterLabel: string
  icon: DataSourceIconMeta
  getTitle: (item: any) => string
  getSuffix: (item: any) => string
  getMetaParts: (item: any) => string[]
  getStatus: (status: string) => DataSourceStatusViewModel
}

type DataSourceTypeDisplayConfigMap = {
  [K in KnowledgeItemType]: DataSourceTypeDisplayConfig
}

const getPathName = (source: string) => {
  const normalizedSource = source.replace(/[/\\]+$/, '')
  const name = normalizedSource.split(/[/\\]/).pop()?.trim()
  return name || normalizedSource || source
}

const getNoteTitle = (content: string) => {
  const firstLine = content
    .split('\n')
    .map((line) => line.trim())
    .find(Boolean)
  return firstLine || ''
}

export const resolveDataSourceStatusViewModel = (status: string): DataSourceStatusViewModel => {
  if (status === 'completed') {
    return {
      kind: 'completed',
      label: '已完成',
      textClassName: 'text-accent-success',
      icon: 'check'
    }
  }
  if (status === 'failed') {
    return {
      kind: 'failed',
      label: '失败',
      textClassName: 'text-accent-danger',
      icon: 'alert'
    }
  }
  if (status === 'embedding') {
    return {
      kind: 'processing',
      label: '嵌入中',
      textClassName: 'text-accent-purple',
      icon: 'loader'
    }
  }
  if (status === 'reading') {
    return {
      kind: 'processing',
      label: '读取中',
      textClassName: 'text-accent-info',
      icon: 'loader'
    }
  }
  if (status === 'processing') {
    return {
      kind: 'processing',
      label: '处理中',
      textClassName: 'text-accent-warning',
      icon: 'loader'
    }
  }
  if (status === 'idle' || status === 'preparing') {
    return {
      kind: 'processing',
      label: '等待中',
      textClassName: 'text-foreground-muted',
      icon: 'loader'
    }
  }
  return {
    kind: 'processing',
    label: '分块中',
    textClassName: 'text-accent-violet',
    icon: 'loader'
  }
}

export const dataSourceTypeDisplayConfig: DataSourceTypeDisplayConfigMap = {
  file: {
    filterLabel: '文件',
    icon: {
      iconClassName: 'text-accent-info'
    },
    getTitle: (item) => getPathName(item.data.source),
    getSuffix: (item) => {
      const name = getPathName(item.data.source)
      const ext = name.includes('.') ? name.split('.').pop() : undefined
      return (ext || 'FILE').toLowerCase()
    },
    getMetaParts: () => [],
    getStatus: resolveDataSourceStatusViewModel
  },
  note: {
    filterLabel: '笔记',
    icon: {
      iconClassName: 'text-accent-amber'
    },
    getTitle: (item) => getNoteTitle(item.data.content),
    getSuffix: () => '',
    getMetaParts: () => [],
    getStatus: resolveDataSourceStatusViewModel
  },
  directory: {
    filterLabel: '目录',
    icon: {
      iconClassName: 'text-accent-violet'
    },
    getTitle: (item) => getPathName(item.data.source),
    getSuffix: () => '',
    getMetaParts: () => [],
    getStatus: resolveDataSourceStatusViewModel
  },
  url: {
    filterLabel: '网址',
    icon: {
      iconClassName: 'text-accent-cyan'
    },
    getTitle: (item) => item.data.source,
    getSuffix: () => '',
    getMetaParts: () => [],
    getStatus: resolveDataSourceStatusViewModel
  }
}
