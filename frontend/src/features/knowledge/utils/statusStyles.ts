export const STATUS_MAP: Record<string, { label: string; color: string; icon: string }> = {
  idle: { label: '待处理', color: 'text-foreground-muted', icon: 'fa-regular fa-circle' },
  preparing: { label: '准备中', color: 'text-accent-warning', icon: 'fa-solid fa-spinner fa-spin' },
  processing: { label: '处理中', color: 'text-accent-warning', icon: 'fa-solid fa-spinner fa-spin' },
  reading: { label: '读取中', color: 'text-accent-info', icon: 'fa-solid fa-book-open' },
  embedding: { label: '嵌入中', color: 'text-accent-purple', icon: 'fa-solid fa-brain' },
  completed: { label: '已完成', color: 'text-accent-success', icon: 'fa-solid fa-check' },
  failed: { label: '失败', color: 'text-accent-danger', icon: 'fa-solid fa-circle-exclamation' },
  deleting: { label: '删除中', color: 'text-foreground-muted', icon: 'fa-solid fa-trash-can' },
};

export const TYPE_ICON_MAP: Record<string, string> = {
  file: 'fa-regular fa-file-lines',
  url: 'fa-solid fa-link',
  note: 'fa-regular fa-note-sticky',
  directory: 'fa-regular fa-folder',
};

export function getItemTitle(item: { id: string; data?: Record<string, any> }): string {
  if (item.data && 'source' in item.data) return (item.data as any).source;
  return item.id.slice(0, 8);
}
