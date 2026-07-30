export const ROUTES = {
  HOME: '/',
  DEMAND: '/workflow/demand',
  PROBLEM: '/workflow/problem',
  PATENTS: '/patents',
  SOLUTION: '/workflow/solution',
  EVALUATION: '/workflow/evaluation',
  VIDEO: '/workflow/video',
  PROJECT: '/history-solutions',
  HISTORY: '/history',
  HISTORY_SOLUTIONS: '/history-solutions',
  KNOWLEDGE: '/knowledge',
  WORKFLOW_DEMAND: '/workflow/demand',
  WORKFLOW_MODELING: '/workflow/modeling',
  ADMIN_KEYS: '/admin/keys',
  ADMIN_USERS: '/admin/users',
  ADMIN_PATENTS: '/admin/patents',
} as const;

export const NAV_ITEMS = [
  { label: '工作台', path: ROUTES.HOME },
  { label: '需求分析', path: ROUTES.DEMAND },
  { label: '问题定义', path: ROUTES.PROBLEM },
  { label: '专利检索', path: ROUTES.PATENTS },
  { label: '方案生成', path: ROUTES.SOLUTION },
  { label: '方案评估', path: ROUTES.EVALUATION },
  { label: '视频展示', path: ROUTES.VIDEO },
  { label: '项目管理', path: ROUTES.PROJECT },
] as const;

export const TASK_STATUS_MAP: Record<string, { label: string; color: string }> = {
  pending: { label: '待处理', color: 'text-yellow-400' },
  analyzing: { label: '分析中', color: 'text-blue-400' },
  completed: { label: '已完成', color: 'text-green-400' },
  failed: { label: '失败', color: 'text-red-400' },
};