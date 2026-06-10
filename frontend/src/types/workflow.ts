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

export const WORKFLOW_STEPS: { phaseId: string; label: string; description: string; icon: string; color: string }[] = [
  { phaseId: 'demand_portrait', label: '需求洞察', description: '理解用户需求，提取关键要素', icon: 'fa-solid fa-magnifying-glass', color: 'var(--accent-blue)' },
  { phaseId: 'problem_modeling', label: '问题建模', description: '构建问题模型，识别核心冲突', icon: 'fa-solid fa-cube', color: 'var(--accent-purple)' },
  { phaseId: 'patent_search', label: '专利检索', description: '检索相关专利，分析技术方案', icon: 'fa-solid fa-file-lines', color: 'var(--accent-cyan)' },
  { phaseId: 'solution_gen', label: '方案生成', description: '生成创新方案，整合多源知识', icon: 'fa-solid fa-wand-magic-sparkles', color: 'var(--accent-green)' },
  { phaseId: 'evaluation', label: '方案评估', description: '评估方案可行性与创新性', icon: 'fa-solid fa-chart-line', color: 'var(--accent-yellow)' },
];
