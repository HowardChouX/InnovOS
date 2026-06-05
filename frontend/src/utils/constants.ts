export const ROUTES = {
  HOME: '/',
  TASKS: '/tasks',
  ANALYSIS: '/analysis',
  PATENTS: '/patents',
  SOLUTIONS: '/solutions',
  EVALUATION: '/evaluation',
  RESULTS: '/results',
  KNOWLEDGE: '/knowledge',
  SETTINGS: '/settings',
} as const;

export const NAV_ITEMS = [
  { label: '首页', path: ROUTES.HOME, icon: 'fa-house' },
  { label: '创新任务', path: ROUTES.TASKS, icon: 'fa-tasks' },
  { label: '问题分析', path: ROUTES.ANALYSIS, icon: 'fa-chart-bar' },
  { label: '专利检索', path: ROUTES.PATENTS, icon: 'fa-file-alt' },
  { label: '方案生成', path: ROUTES.SOLUTIONS, icon: 'fa-lightbulb' },
  { label: '方案评估', path: ROUTES.EVALUATION, icon: 'fa-chart-line' },
  { label: '成果管理', path: ROUTES.RESULTS, icon: 'fa-folder-open' },
  { label: '知识库管理', path: ROUTES.KNOWLEDGE, icon: 'fa-database' },
  { label: '系统设置', path: ROUTES.SETTINGS, icon: 'fa-cog' },
] as const;

export const TASK_STATUS_MAP: Record<string, { label: string; color: string }> = {
  pending: { label: '待处理', color: 'text-yellow-400' },
  analyzing: { label: '分析中', color: 'text-blue-400' },
  completed: { label: '已完成', color: 'text-green-400' },
  failed: { label: '失败', color: 'text-red-400' },
};
