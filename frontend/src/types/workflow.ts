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
    phaseId: 'demand_portrait',
    label: '需求洞察',
    description: '理解用户需求，提取关键要素',
    color: 'var(--accent-blue)',
  },
  {
    phaseId: 'problem_modeling',
    label: '问题建模',
    description: '构建问题模型，识别核心冲突',
    color: 'var(--accent-purple)',
  },
  {
    phaseId: 'patent_search',
    label: '专利检索',
    description: '检索相关专利，分析技术方案',
    color: 'var(--accent-cyan)',
  },
  {
    phaseId: 'solution_gen',
    label: '方案生成',
    description: '生成创新方案，整合多源知识',
    color: 'var(--accent-green)',
  },
  {
    phaseId: 'evaluation',
    label: '方案评估',
    description: '评估方案可行性与创新性',
    color: 'var(--accent-yellow)',
  },
  {
    phaseId: 'conversion',
    label: '成果转化',
    description: '侵权风险分析与规避设计建议',
    color: 'var(--accent-red)',
  },
];
