import type { KnowledgeItem } from '../../../../../types/knowledge'
import { dataSourceTypeDisplayConfig, type KnowledgeItemRowViewModel } from './models'

export const getItemStatus = (item: KnowledgeItem) => {
  return dataSourceTypeDisplayConfig[item.type].getStatus(item.status)
}

export const getItemTitle = (item: KnowledgeItem): string => {
  return dataSourceTypeDisplayConfig[item.type].getTitle(item)
}

export const getReadyCount = (items: KnowledgeItem[]) =>
  items.reduce((readyCount, item) => readyCount + (item.status === 'completed' ? 1 : 0), 0)

export const toKnowledgeItemRowViewModel = (
  item: KnowledgeItem
): KnowledgeItemRowViewModel => {
  const config = dataSourceTypeDisplayConfig[item.type]
  return {
    title: config.getTitle(item),
    suffix: config.getSuffix(item),
    metaParts: config.getMetaParts(item),
    icon: config.icon,
    status: config.getStatus(item.status)
  }
}
