export const ROUTES = {
  HOME: '/',
  PATENTS: '/patents',
  KNOWLEDGE: '/knowledge',
  HISTORY: '/history',
  HISTORY_SOLUTIONS: '/history-solutions',
  WORKFLOW_DEMAND: '/workflow/demand',
  WORKFLOW_MODELING: '/workflow/modeling',
  ADMIN_KEYS: '/admin/keys',
  ADMIN_USERS: '/admin/users',
  ADMIN_PATENTS: '/admin/patents',
} as const;

export const NAV_ITEMS = [
  { label: '首页', path: ROUTES.HOME, icon: 'fa-house' },
  { label: '历史方案库', path: ROUTES.HISTORY_SOLUTIONS, icon: 'fa-clock-rotate-left' },
  { label: '知识库', path: ROUTES.KNOWLEDGE, icon: 'fa-book' },
  { label: '专利检索', path: ROUTES.PATENTS, icon: 'fa-file-alt' },
] as const;

export const TASK_STATUS_MAP: Record<string, { label: string; color: string }> = {
  pending: { label: '待处理', color: 'text-yellow-400' },
  analyzing: { label: '分析中', color: 'text-blue-400' },
  completed: { label: '已完成', color: 'text-green-400' },
  failed: { label: '失败', color: 'text-red-400' },
};
