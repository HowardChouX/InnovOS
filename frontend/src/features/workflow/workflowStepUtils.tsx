/* eslint-disable react-refresh/only-export-components */
import type { WorkflowState } from '../../types/workflow';

const PHASE_TO_AGENT: Record<string, string> = {
  demand_analysis: 'agent1',
  problem_definition: 'agent2',
  patent_search: 'agent5',
  solution_gen: 'agent3',
  evaluation: 'agent4',
  // video_display: mock 阶段，无后端 agent
};

export function getStepOutput(workflow: WorkflowState | null, phaseId: string): unknown {
  if (!workflow?.steps) return null;
  const agentId = PHASE_TO_AGENT[phaseId];
  if (!agentId) return null;
  const step = workflow.steps.find((s) => (s.agentId || s.agent_id) === agentId);
  if (!step || !step.output) return null;
  try {
    return JSON.parse(step.output);
  } catch {
    return step.output;
  }
}

export function EmptyState({ msg, icon }: { msg: string; icon: string }) {
  return (
    <div
      className="card"
      style={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        minHeight: 260,
        padding: 40,
        flex: 1,
      }}
    >
      <i
        className={icon}
        style={{
          fontSize: 48,
          color: 'var(--text-tertiary)',
          opacity: 0.3,
          marginBottom: 16,
          display: 'block',
        }}
      />
      <p style={{ fontSize: 13, color: 'var(--text-secondary)', margin: 0 }}>{msg}</p>
    </div>
  );
}
