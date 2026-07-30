export type AgentType = 'problem_analysis' | 'patent_search' | 'solution_gen' | 'evaluation';
export type AgentStatus = 'pending' | 'running' | 'completed' | 'failed';

export interface AgentStep {
  agentId?: string;
  agent_id?: string;
  agentType: AgentType;
  agentLabel: string;
  status: AgentStatus;
  description: string;
  startedAt?: string;
  completedAt?: string;
  duration?: string;
  output?: string;
}

export interface WorkflowState {
  id: string;
  // taskId is numeric (backend uses int path params), but stored as string for route consistency
  taskId: string;
  status: 'idle' | 'running' | 'completed' | 'failed' | 'awaiting_rating';
  steps: AgentStep[];
  createdAt: string;
}

export const WORKFLOW_STEPS: {
  phaseId: string;
  label: string;
  description: string;
  color: string;
}[] = [
  {
    phaseId: 'demand_analysis',
    label: '需求分析',
    description: '收集需求，分析背景，明确创新目标',
    color: 'var(--accent-blue)',
  },
  {
    phaseId: 'problem_definition',
    label: '问题定义',
    description: '定位核心障碍，定义关键矛盾',
    color: 'var(--accent-purple)',
  },
  {
    phaseId: 'patent_search',
    label: '专利/知识检索',
    description: '检索专利与知识，洞察现有技术与空白',
    color: 'var(--accent-cyan)',
  },
  {
    phaseId: 'solution_gen',
    label: '创新方案生成',
    description: 'AI辅助启发式多版创新方案',
    color: 'var(--accent-green)',
  },
  {
    phaseId: 'evaluation',
    label: '方案评估',
    description: '多维评估，筛选优化，形成最优方案',
    color: 'var(--accent-yellow)',
  },
];