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
