export const ROUTES = {
  HOME: '/',
  PATENTS: '/patents',
  KNOWLEDGE: '/knowledge',
  MONITOR: '/monitor',
  HISTORY: '/history',
  PATENT_CONVERSION: '/patent-conversion',
  WORKFLOW_DEMAND: '/workflow/demand',
  WORKFLOW_MODELING: '/workflow/modeling',
  ADMIN_KEYS: '/admin/keys',
  ADMIN_USERS: '/admin/users',
} as const;

export const NAV_ITEMS = [
  { label: '首页', path: ROUTES.HOME, icon: 'fa-house' },
  { label: '知识库', path: ROUTES.KNOWLEDGE, icon: 'fa-book' },
  { label: '历史方案', path: ROUTES.HISTORY, icon: 'fa-clock-rotate-left' },
  { label: '专利检索', path: ROUTES.PATENTS, icon: 'fa-file-alt' },
  { label: '专利转化', path: ROUTES.PATENT_CONVERSION, icon: 'fa-file-contract' },
] as const;

export const TASK_STATUS_MAP: Record<string, { label: string; color: string }> = {
  pending: { label: '待处理', color: 'text-yellow-400' },
  analyzing: { label: '分析中', color: 'text-blue-400' },
  completed: { label: '已完成', color: 'text-green-400' },
  failed: { label: '失败', color: 'text-red-400' },
};
