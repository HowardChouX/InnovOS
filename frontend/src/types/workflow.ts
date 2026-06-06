export type AgentType = 'problem_analysis' | 'patent_search' | 'solution_gen' | 'evaluation';
export type AgentStatus = 'pending' | 'running' | 'completed' | 'failed';

export interface AgentStep {
  agentId: string;
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
  taskId: string;
  status: 'idle' | 'running' | 'completed' | 'failed';
  steps: AgentStep[];
  createdAt: string;
}

export const WORKFLOW_STEPS: { agentId: string; agentType: AgentType; label: string; description: string; icon: string; color: string }[] = [
  { agentId: 'agent1', agentType: 'problem_analysis', label: '需求洞察Agent', description: '理解用户需求，提取关键要素', icon: 'fa-solid fa-magnifying-glass', color: 'var(--accent-blue)' },
  { agentId: 'agent2', agentType: 'patent_search', label: '问题建模Agent', description: '构建问题模型，识别核心冲突', icon: 'fa-solid fa-cube', color: 'var(--accent-purple)' },
  { agentId: 'agent5', agentType: 'patent_search', label: '专利分析Agent', description: '检索相关专利，分析技术方案', icon: 'fa-solid fa-file-lines', color: 'var(--accent-cyan)' },
  { agentId: 'agent3', agentType: 'solution_gen', label: '方案生成Agent', description: '生成创新方案，整合多源知识', icon: 'fa-solid fa-wand-magic-sparkles', color: 'var(--accent-green)' },
  { agentId: 'agent4', agentType: 'evaluation', label: '方案评估Agent', description: '评估方案可行性与创新性', icon: 'fa-solid fa-chart-line', color: 'var(--accent-yellow)' },
  { agentId: 'agent6', agentType: 'evaluation', label: '成果转化Agent', description: '输出结构化成果，支持转化', icon: 'fa-solid fa-arrow-right-arrow-left', color: 'var(--accent-red)' },
];
